#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KeySwitch v2 配置迁移：config.yaml 加 label/mapping + codex target + 补齐 key 池

运行：python scripts/update_config_v2.py
安全：只读旧配置的 key 值，追加/修改结构字段，key 明文不打印。
"""
import json
import os
import re
import subprocess
import sys
import yaml

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(BASE, "config", "config.yaml")


def get_actual():
    """读各软件实际生效 key（返回 dict name -> key_value）"""
    a = {}
    try:
        d = json.load(open(os.path.expanduser("~/.pi/agent/auth.json"), encoding="utf-8"))
        a["pi"] = d.get("opencode-go", {}).get("key", "")
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "[Environment]::GetEnvironmentVariable('OPENCODE_GO_API_KEY','User')"],
            capture_output=True, text=True, timeout=60)
        a["hermes_dsh"] = r.stdout.strip()
    except Exception:
        pass
    try:
        txt = open(os.path.expanduser("~/AppData/Roaming/OpenChatCut/.env.local"),
                   encoding="utf-8").read()
        m = re.search(r"^LLM_DEEPSEEK_API_KEY=(.+)$", txt, re.M)
        a["openchatcut"] = m.group(1).strip() if m else ""
    except Exception:
        pass
    try:
        d = json.load(open(os.path.expanduser("~/.workbuddy/models.json"), encoding="utf-8"))
        keys = {m.get("apiKey") for m in d if m.get("apiKey")}
        a["workbuddy"] = next(iter(keys), "")
    except Exception:
        pass
    try:
        a["codex"] = open(os.path.expanduser(
            "~/.codex/codex-router/opencode-go-api-key.secret"),
            encoding="utf-8").read().strip()
    except Exception:
        pass
    return a


def main():
    cfg = yaml.safe_load(open(CFG, encoding="utf-8"))
    actual = get_actual()

    # 1) 池内已有 key 值集合
    pool_values = set()
    for p, pc in cfg["providers"].items():
        for k in pc.get("keys", []):
            if k.get("key"):
                pool_values.add(k["key"])

    # 2) opencode-go: 确保 opencode-3 有值（pi 新 key）、追加 opencode-4（codex 独立 key）
    og = cfg["providers"]["opencode-go"]
    for k in og["keys"]:
        if k["id"] == "opencode-3" and not k.get("key"):
            if actual.get("pi") and actual["pi"] not in pool_values:
                k["key"] = actual["pi"]
                k["note"] = "pi 在用"
                pool_values.add(actual["pi"])
        if k["id"] == "opencode-2" and k.get("note", "").find("pi 在用") >= 0:
            k["note"] = "备用"
    og_ids = {k["id"] for k in og["keys"]}
    if actual.get("codex") and actual["codex"] not in pool_values and "opencode-4" not in og_ids:
        og["keys"].append({"id": "opencode-4", "key": actual["codex"], "note": "Codex 在用"})
        pool_values.add(actual["codex"])

    # 3) targets 加 label + mapping（按实际生效 key 反查池内 id）
    def find_id(v):
        if not v:
            return ""
        for p, pc in cfg["providers"].items():
            for k in pc.get("keys", []):
                if k.get("key") == v:
                    return k["id"]
        return ""

    labels = {
        "pi": "pi 工具",
        "hermes_dsh": "Hermes + DSH",
        "openchatcut": "OpenChatCut",
        "workbuddy": "WorkBuddy",
        "codex": "Codex (codex-router)",
    }
    for t in cfg.get("targets", []):
        t.setdefault("label", labels.get(t["name"], t["name"]))
        t["mapping"] = {"opencode-go": find_id(actual.get(t["name"], ""))}
    # 加 codex target
    names = {t["name"] for t in cfg["targets"]}
    if "codex" not in names:
        cfg["targets"].append({
            "name": "codex", "label": "Codex (codex-router)",
            "adapter": "codex",
            "mapping": {"opencode-go": find_id(actual.get("codex", ""))},
        })

    with open(CFG, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    # 打印结果（打码）
    print("=== 迁移完成 ===")
    for t in cfg["targets"]:
        m = {p: v for p, v in t.get("mapping", {}).items() if v}
        print(f"  {t['name']:<12} label={t.get('label')} mapping={m}")
    for p, pc in cfg["providers"].items():
        for k in pc.get("keys", []):
            kv = k.get("key", "")
            disp = kv[:6] + "..." + kv[-6:] if kv else "(空)"
            print(f"  {k['id']:<12} {disp}  note={k.get('note','')}")


if __name__ == "__main__":
    main()
