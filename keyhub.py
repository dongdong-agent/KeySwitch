#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API Key 管理器 v2 - 核心引擎（每软件独立映射）

模型：providers 定义 key 池；targets 定义软件，每个软件有独立 mapping
（provider -> key_id）。界面/CLI 按 mapping 写入各软件，互不影响。

CLI：
  status                查看所有 key 用量状态 + 各软件实际生效 key
  apply <target>        应用单个软件的 mapping（写该软件）
  apply-all             应用所有软件 mapping
  auto                  检测所有在用 key 用量，告急打印提示
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import yaml

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)  # 打包后：exe 所在目录（配置可持久化）
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config", "config.yaml")

from adapters.pi import PiAdapter
from adapters.env_var import EnvVarAdapter
from adapters.openchatcut import OpenChatCutAdapter
from adapters.workbuddy import WorkBuddyAdapter
from adapters.codex import CodexAdapter
from adapters.file_adapters import JsonFileAdapter, EnvFileAdapter, RegexFileAdapter

ADAPTER_FACTORY = {
    "pi": PiAdapter,
    "env_var": EnvVarAdapter,
    "openchatcut": OpenChatCutAdapter,
    "workbuddy": WorkBuddyAdapter,
    "codex": CodexAdapter,
    "file_json": JsonFileAdapter,
    "file_env": EnvFileAdapter,
    "file_regex": RegexFileAdapter,
}


# ---------- 配置 ----------

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        # 首次运行 / 发布版：自动生成空模板，避免直接退出
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            template = {"thresholds": {}, "providers": {}, "targets": [],
                        "auto_switch": {"enabled": False, "interval_min": 5,
                                        "trigger_percent": 100}}
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.safe_dump(template, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            sys.exit(f"配置不存在且无法自动生成: {CONFIG_PATH}（{e}）")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def build_adapters(cfg: dict) -> dict:
    """返回 {target_name: adapter}，按 target 配置带参实例化"""
    out = {}
    for t in cfg.get("targets", []):
        name = t.get("adapter")
        cls = ADAPTER_FACTORY.get(name)
        if not cls:
            print(f"[warn] 未知适配器: {name} (target {t.get('name')})")
            continue
        try:
            if name == "env_var":
                a = cls(env_name=t.get("env", "OPENCODE_GO_API_KEY"),
                        restart=t.get("restart_hint", []))
            elif name == "file_json":
                a = cls(path=t.get("path", ""), key_path=t.get("key_path", "api_key"))
            elif name == "file_env":
                a = cls(path=t.get("path", ""), key_name=t.get("key_name", "API_KEY"))
            elif name == "file_regex":
                a = cls(path=t.get("path", ""), pattern=t.get("pattern", ""),
                        replacement=t.get("replacement", "\\1{key}\\2"))
            else:
                a = cls()
            out[t["name"]] = a
        except Exception as e:
            print(f"[warn] 适配器实例化失败 {t.get('name')}: {e}")
    return out


def find_key(cfg: dict, provider: str, key_id: str) -> str:
    for k in cfg["providers"].get(provider, {}).get("keys", []):
        if k.get("id") == key_id:
            return k.get("key", "")
    return ""


def key_ids(cfg: dict, provider: str) -> list:
    return [k.get("id") for k in cfg["providers"].get(provider, {}).get("keys", [])]


def provider_names(cfg: dict) -> list:
    return list(cfg.get("providers", {}).keys())


def target_mapping(cfg: dict, target_name: str) -> dict:
    for t in cfg.get("targets", []):
        if t.get("name") == target_name:
            return dict(t.get("mapping", {}))
    return {}


# ---------- 写入（按 mapping） ----------

def apply_target(cfg: dict, adapters: dict, target_name: str,
                 mapping: dict | None = None) -> dict:
    """应用单个软件的 mapping。返回 {results: [...], restart: [...]}"""
    if target_name not in adapters:
        return {"results": [{"target": target_name, "ok": False,
                             "msg": "适配器不存在"}], "restart": []}
    a = adapters[target_name]
    mapping = mapping if mapping is not None else target_mapping(cfg, target_name)
    results = []
    for provider, key_id in mapping.items():
        if not key_id or key_id == "__none__":
            continue
        key = find_key(cfg, provider, key_id)
        if not key:
            results.append({"target": target_name, "provider": provider,
                            "ok": False, "msg": f"key 为空: {provider}/{key_id}"})
            continue
        r = a.write_key(provider, key)
        r["target"] = target_name
        r["provider"] = provider
        results.append(r)
    return {"results": results, "restart": a.restart_hint()}


def apply_all(cfg: dict, adapters: dict) -> dict:
    all_results = []
    restart = set()
    for t in cfg.get("targets", []):
        r = apply_target(cfg, adapters, t["name"])
        all_results.extend(r["results"])
        restart.update(r["restart"])
    return {"results": all_results, "restart": sorted(restart)}


def read_actual_all(cfg: dict, adapters: dict) -> dict:
    """返回 {target_name: {provider: 实际key值}}"""
    out = {}
    for t in cfg.get("targets", []):
        name = t["name"]
        a = adapters.get(name)
        if not a:
            continue
        out[name] = {}
        for provider in provider_names(cfg):
            out[name][provider] = a.read_key(provider)
    return out


# ---------- 用量检测 ----------

def http_get_json(url: str, key: str, timeout: int = 15) -> dict | None:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"_error": str(e)}


def query_usage(provider_cfg: dict, key: str) -> dict:
    utype = provider_cfg.get("usage_type", "percent")
    base = provider_cfg.get("base_url", "")
    if utype == "balance":
        d = http_get_json(f"{base}/user/balance", key)
        if not d or "_error" in d:
            return {"type": "balance", "percent": None, "balance": None,
                    "status": "error", "detail": d.get("_error", "查询失败") if d else "无响应"}
        infos = d.get("balance_infos") or []
        total = sum(float(i.get("total_balance", 0)) for i in infos) if infos else 0.0
        return {"type": "balance", "percent": None, "balance": total,
                "status": "ok" if d.get("is_available", True) else "disabled",
                "detail": f"余额 ¥{total:.2f}"}
    d = http_get_json(f"{base}/usage", key)
    if not d or "_error" in d:
        return {"type": "percent", "percent": None, "balance": None,
                "status": "error", "detail": d.get("_error", "查询失败") if d else "无响应"}
    usage = d.get("usage", {})
    rolling = usage.get("rolling", {})
    pct = rolling.get("percent")
    st = rolling.get("status", "ok")
    return {"type": "percent", "percent": pct, "balance": None, "status": st,
            "detail": f"滚动{pct}% / 周{usage.get('weekly',{}).get('percent','?')}% / 月{usage.get('monthly',{}).get('percent','?')}%"}


def is_exhausted(cfg: dict, provider: str, usage: dict,
                 trigger_percent: int | None = None) -> bool:
    """判定 key 用量是否告急/不可用。

    trigger_percent 覆盖 thresholds.<provider>.percent（智能切换用，
    默认 100 = 用量打满才判定耗尽；普通告急提示用 90）。
    """
    thr = cfg.get("thresholds", {}).get(provider, {})
    if usage["status"] in ("error", "disabled"):
        return True
    if usage["type"] == "balance":
        return usage.get("balance", 999) < thr.get("balance_min", 5)
    pct = usage.get("percent")
    if pct is None:
        return True
    limit = trigger_percent if trigger_percent is not None else thr.get("percent", 90)
    return pct >= limit


def status_all(cfg: dict) -> list:
    out = []
    for pname, pcfg in cfg.get("providers", {}).items():
        for k in pcfg.get("keys", []):
            kid = k.get("id")
            key = k.get("key", "")
            if not key:
                out.append({"provider": pname, "id": kid, "key_prefix": "(空)",
                            "usage": None, "note": k.get("note", "")})
                continue
            usage = query_usage(pcfg, key)
            out.append({"provider": pname, "id": kid, "key_prefix": key[:8],
                        "usage": usage, "note": k.get("note", "")})
    return out


def list_adapters() -> dict:
    """返回 {adapter名: 说明}，供界面「添加应用」选型"""
    return {name: cls.description for name, cls in ADAPTER_FACTORY.items()}


# ---------- 管理（增删 provider / key / 应用） ----------

def add_provider(cfg: dict, name: str, base_url: str = "",
                 usage_type: str = "percent", threshold: dict | None = None) -> tuple:
    providers = cfg.setdefault("providers", {})
    if name in providers:
        return False, f"Provider 已存在: {name}"
    providers[name] = {"base_url": base_url, "usage_type": usage_type, "keys": []}
    if threshold:
        cfg.setdefault("thresholds", {})[name] = threshold
    return True, f"已添加 Provider {name}（请接着添加 key）"


def add_key(cfg: dict, provider: str, key_id: str, key_value: str,
            note: str = "") -> tuple:
    providers = cfg.get("providers", {})
    if provider not in providers:
        return False, f"Provider 不存在: {provider}"
    keys = providers[provider].setdefault("keys", [])
    if any(k.get("id") == key_id for k in keys):
        return False, f"key id 已存在: {provider}/{key_id}"
    keys.append({"id": key_id, "key": key_value, "note": note})
    return True, f"已添加 {provider}/{key_id}"


def delete_key(cfg: dict, provider: str, key_id: str) -> tuple:
    keys = cfg.get("providers", {}).get(provider, {}).get("keys", [])
    new = [k for k in keys if k.get("id") != key_id]
    if len(new) == len(keys):
        return False, f"未找到 {provider}/{key_id}"
    cfg["providers"][provider]["keys"] = new
    # 清理引用该 key 的 mapping（置空 = 不使用）
    for t in cfg.get("targets", []):
        m = t.get("mapping", {})
        for p, kid in list(m.items()):
            if kid == key_id:
                m[p] = ""
    return True, f"已删除 {provider}/{key_id}"


def delete_provider(cfg: dict, name: str) -> tuple:
    providers = cfg.get("providers", {})
    if name not in providers:
        return False, f"Provider 不存在: {name}"
    del providers[name]
    cfg.get("thresholds", {}).pop(name, None)
    for t in cfg.get("targets", []):
        t.get("mapping", {}).pop(name, None)
    return True, f"已删除 Provider {name}"


def add_target(cfg: dict, name: str, label: str, adapter: str,
               params: dict | None = None, mapping: dict | None = None) -> tuple:
    if any(t.get("name") == name for t in cfg.get("targets", [])):
        return False, f"应用已存在: {name}"
    t = {"name": name, "label": label, "adapter": adapter}
    if params:
        t.update(params)
    t["mapping"] = mapping or {}
    cfg.setdefault("targets", []).append(t)
    return True, f"已添加应用「{label}」（保存后写入其配置）"


def delete_target(cfg: dict, name: str) -> tuple:
    targets = cfg.get("targets", [])
    new = [t for t in targets if t.get("name") != name]
    if len(new) == len(targets):
        return False, f"未找到应用: {name}"
    cfg["targets"] = new
    return True, f"已删除应用 {name}"


# ---------- 智能切换（按优先级自动换 key） ----------

def smart_switch_once(cfg: dict, adapters: dict, trigger_percent: int | None = None) -> dict:
    """检测所有「在用 key」（出现在任一软件 mapping 里），耗尽的按优先级
    自动切到该 provider 第一个可用 key（keys 列表顺序 = 优先级，越靠上越优）。

    返回 {'switches': [{provider, from, to, targets, ok}], 'exhausted': [...], 'checked': N}
    """
    trigger = trigger_percent
    if trigger is None:
        trigger = cfg.get("auto_switch", {}).get("trigger_percent", 100)

    # 1) 收集在用 key → 使用它的软件
    usage_map = {}
    for t in cfg.get("targets", []):
        for p, kid in t.get("mapping", {}).items():
            if kid:
                usage_map.setdefault((p, kid), []).append(t["name"])

    switches = []
    exhausted = []
    for (provider, kid), targets in usage_map.items():
        pcfg = cfg.get("providers", {}).get(provider, {})
        key = find_key(cfg, provider, kid)
        if not key:
            continue
        usage = query_usage(pcfg, key)
        if not is_exhausted(cfg, provider, usage, trigger):
            continue
        exhausted.append(f"{provider}/{kid}")
        # 2) 按优先级（列表顺序）找第一个可用 key，跳过自身
        best = None
        for k in pcfg.get("keys", []):
            if k.get("id") == kid or not k.get("key"):
                continue
            ku = query_usage(pcfg, k["key"])
            if not is_exhausted(cfg, provider, ku, trigger):
                best = k["id"]
                break
        if not best:
            continue
        # 3) 切换所有使用该 key 的软件
        new_val = find_key(cfg, provider, best)
        ok_targets = []
        fail_targets = []
        for tname in targets:
            t = next((x for x in cfg.get("targets", []) if x.get("name") == tname), None)
            if not t:
                continue
            a = adapters.get(tname)
            r = a.write_key(provider, new_val) if a else {"ok": False, "msg": "无适配器"}
            t["mapping"][provider] = best
            (ok_targets if r.get("ok") else fail_targets).append(tname)
        switches.append({"provider": provider, "from": kid, "to": best,
                         "targets": ok_targets, "failed": fail_targets})

    # ⚠️ 本函数不自动写盘：调用方确认 cfg 可信后自行 save_config(cfg)
    return {"switches": switches, "exhausted": exhausted, "checked": len(usage_map)}


def use_key(cfg: dict, adapters: dict, provider: str, key_id: str) -> dict:
    """手动切换：把该 provider 下所有「正在使用」的软件统一切换到指定 key。

    只切换 mapping[provider] 非空（正在使用该 provider）的软件；
    未使用该 provider 的软件保持原样，不强制写入。
    返回 {'provider', 'key_id', 'targets': [...], 'restart': [...], 'error': str}
    """
    if provider not in cfg.get("providers", {}):
        return {"provider": provider, "key_id": key_id, "targets": [],
                "restart": [], "error": f"Provider 不存在: {provider}"}
    key = find_key(cfg, provider, key_id)
    if not key:
        return {"provider": provider, "key_id": key_id, "targets": [],
                "restart": [], "error": f"未找到 {provider}/{key_id} 的 key 值"}
    ok_targets = []
    restart = set()
    for t in cfg.get("targets", []):
        m = t.get("mapping", {})
        if not m.get(provider):
            continue  # 该软件未使用此 provider，不动
        a = adapters.get(t["name"])
        r = a.write_key(provider, key) if a else {"ok": False, "msg": "无适配器"}
        m[provider] = key_id  # 无论写入成败都更新意图（与智能切换一致）
        if r.get("ok"):
            ok_targets.append(t["name"])
            restart.update(a.restart_hint() if a else [])
        else:
            ok_targets.append(f"{t['name']}（写入失败: {r.get('msg', '')}）")
    return {"provider": provider, "key_id": key_id,
            "targets": ok_targets, "restart": sorted(restart), "error": ""}


def move_key(cfg: dict, provider: str, key_id: str, direction: str) -> tuple:
    """调整 key 优先级（keys 列表顺序 = 优先级，越靠前越优先）。direction: up/down"""
    keys = cfg.get("providers", {}).get(provider, {}).get("keys", [])
    idx = next((i for i, k in enumerate(keys) if k.get("id") == key_id), None)
    if idx is None:
        return False, f"未找到 {provider}/{key_id}"
    ni = idx - 1 if direction == "up" else idx + 1
    if ni < 0 or ni >= len(keys):
        return False, f"{key_id} 已在{'最前' if direction == 'up' else '最后'}"
    keys[idx], keys[ni] = keys[ni], keys[idx]
    return True, f"{provider}/{key_id} 已{'上移' if direction == 'up' else '下移'}（顺序即优先级）"


# ---------- CLI ----------

def cmd_status(cfg: dict, adapters: dict):
    print("=== Key 用量 ===")
    for s in status_all(cfg):
        if s["usage"] is None:
            print(f"  {s['provider']:<12} {s['id']:<12} (未配置)  {s['note']}")
            continue
        u = s["usage"]
        print(f"  {s['provider']:<12} {s['id']:<12} 状态:{u['status']:<8} {u['detail']}  {s['note']}")
    print("\n=== 各软件实际生效 key ===")
    actual = read_actual_all(cfg, adapters)
    for t in cfg.get("targets", []):
        name = t["name"]
        parts = []
        for provider, v in actual.get(name, {}).items():
            if v:
                parts.append(f"{provider}: {v[:6]}...{v[-6:]}")
        print(f"  {name:<12} {t.get('label','')}  {'; '.join(parts) if parts else '(未配置)'}")


def cmd_apply(cfg: dict, adapters: dict, target_name: str):
    r = apply_target(cfg, adapters, target_name)
    for res in r["results"]:
        flag = "✅" if res["ok"] else "❌"
        print(f"  {flag} [{res['target']}]{res.get('provider','')} {res['msg']}")
    if r["restart"]:
        print(f"\n⚠️ 需重启生效: {', '.join(r['restart'])}")


def cmd_apply_all(cfg: dict, adapters: dict):
    r = apply_all(cfg, adapters)
    for res in r["results"]:
        flag = "✅" if res["ok"] else "❌"
        print(f"  {flag} [{res['target']}]{res.get('provider','')} {res['msg']}")
    if r["restart"]:
        print(f"\n⚠️ 需重启生效: {', '.join(r['restart'])}")


def cmd_auto(cfg: dict):
    """检测所有在 mapping 中用到的 key，告急打印提示（不自动写）"""
    used = set()
    for t in cfg.get("targets", []):
        for provider, kid in t.get("mapping", {}).items():
            if kid and kid != "__none__":
                used.add((provider, kid))
    print("=== 在用 key 用量检测 ===")
    for provider, kid in sorted(used):
        key = find_key(cfg, provider, kid)
        if not key:
            print(f"  {provider}/{kid}: (未配置)")
            continue
        usage = query_usage(cfg["providers"].get(provider, {}), key)
        warn = " ⚠️ 告急!" if is_exhausted(cfg, provider, usage) else ""
        print(f"  {provider:<12} {kid:<12} 状态:{usage['status']:<8} {usage['detail']}{warn}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cfg = load_config()
    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status(cfg, build_adapters(cfg))
    elif cmd == "apply" and len(sys.argv) >= 3:
        cmd_apply(cfg, build_adapters(cfg), sys.argv[2])
    elif cmd == "apply-all":
        cmd_apply_all(cfg, build_adapters(cfg))
    elif cmd == "auto":
        cmd_auto(cfg)
    elif cmd == "smart":
        r = smart_switch_once(cfg, build_adapters(cfg))
        if r["switches"]:
            save_config(cfg)
        print(f"检测 {r['checked']} 个在用 key")
        for s in r["switches"]:
            print(f"  🔄 {s['provider']}: {s['from']} → {s['to']}（软件: {', '.join(s['targets']) or '无'}）")
        if r["exhausted"]:
            print(f"  ⚠️ 告急但无可用 key: {', '.join(r['exhausted'])}")
        if not r["switches"] and not r["exhausted"]:
            print("  ✅ 全部正常")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
