#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迁移：Python 版 KeySwitch 配置 → Rust 版 TOML 配置

用法：python tools/migrate_config.py [旧yaml路径]
默认读 /l/00-projects/apikey-switcher/config/config.yaml，
写入 %APPDATA%/KeySwitch/config.toml（Rust 版读取位置）。
"""
import os
import sys
import yaml

OLD = sys.argv[1] if len(sys.argv) > 1 else r"L:\00-projects\apikey-switcher\config\config.yaml"
NEW = os.path.join(os.environ.get("APPDATA", r"C:\Users\vista\AppData\Roaming"), "KeySwitch", "config.toml")


def to_toml(cfg: dict) -> str:
    """把 Python 版 config 转成 Rust 版 TOML 文本"""
    lines = []

    # thresholds
    thr = cfg.get("thresholds") or {}
    if thr:
        lines.append("[thresholds]")
        for p, t in thr.items():
            pairs = ", ".join(f"{k} = {v}" for k, v in t.items())
            lines.append(f'[thresholds.{p}]')
            for k, v in t.items():
                lines.append(f"{k} = {v}")
        lines.append("")

    # providers
    lines.append("[auto_switch]")
    auto = cfg.get("auto_switch") or {}
    lines.append(f"enabled = {'true' if auto.get('enabled') else 'false'}")
    lines.append(f"interval_min = {auto.get('interval_min', 5)}")
    lines.append(f"trigger_percent = {auto.get('trigger_percent', 100)}")
    lines.append("")

    for pname, pc in (cfg.get("providers") or {}).items():
        lines.append(f"[providers.{pname}]")
        lines.append(f'base_url = "{pc.get("base_url", "")}"')
        lines.append(f'usage_type = "{pc.get("usage_type", "percent")}"')
        for i, k in enumerate(pc.get("keys") or []):
            note = k.get("note", "")
            note_toml = f', note = "{note}"' if note else ""
            lines.append(f'[[providers.{pname}.keys]]')
            lines.append(f'id = "{k.get("id", "")}"')
            # key 值直接嵌入（含特殊字符转义）
            lines.append(f'key = "{k.get("key", "").replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"')
            if note:
                lines.append(f'note = "{note}"')
        lines.append("")

    # targets
    for i, t in enumerate(cfg.get("targets") or []):
        lines.append(f"[[targets]]")
        lines.append(f'name = "{t.get("name", "")}"')
        lines.append(f'label = "{t.get("label", t.get("name", ""))}"')
        lines.append(f'adapter = "{t.get("adapter", "")}"')
        for key in ("env", "path", "key_path", "key_name", "pattern", "replacement"):
            v = t.get(key)
            if v:
                v_esc = v.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{v_esc}"')
        for p, kid in (t.get("mapping") or {}).items():
            if kid:
                lines.append(f'[targets.{i}.mapping.{p}]')
                # 简化：直接写标量
        # 上面 mapping 用数组式不可行，改为 mapping 放键值——TOML 嵌套表
    # targets mapping 单独处理（上一步简化失败，重新构建）
    # 重新生成 targets（mapping 用 [targets.N.mapping] 表）
    out = []
    out.append("[auto_switch]")
    out.append(f"enabled = {'true' if auto.get('enabled') else 'false'}")
    out.append(f"interval_min = {auto.get('interval_min', 5)}")
    out.append(f"trigger_percent = {auto.get('trigger_percent', 100)}")
    out.append("")
    for pname, pc in (cfg.get("providers") or {}).items():
        out.append(f"[providers.{pname}]")
        out.append(f'base_url = "{pc.get("base_url", "")}"')
        out.append(f'usage_type = "{pc.get("usage_type", "percent")}"')
        for k in pc.get("keys") or []:
            out.append(f"[[providers.{pname}.keys]]")
            out.append(f'id = "{k.get("id", "")}"')
            out.append(f'key = "{k.get("key", "").replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"')
            note = k.get("note", "")
            if note:
                out.append(f'note = "{note.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"')
        out.append("")
    for i, t in enumerate(cfg.get("targets") or []):
        out.append(f"[[targets]]")
        out.append(f'name = "{t.get("name", "")}"')
        out.append(f'label = "{t.get("label", t.get("name", ""))}"')
        out.append(f'adapter = "{t.get("adapter", "")}"')
        for key in ("env", "path", "key_path", "key_name", "pattern", "replacement"):
            v = t.get(key)
            if v:
                out.append(f'{key} = "{v.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"')
        mapping = t.get("mapping") or {}
        mapping_items = ", ".join(
            f'{p} = "{kid}"' for p, kid in mapping.items() if kid
        )
        if mapping_items:
            # 内联表：TOML 数组元素内的子映射最可靠的写法
            out.append(f"mapping = {{ {mapping_items} }}")
        out.append("")
    return "\n".join(out)


def main():
    cfg = yaml.safe_load(open(OLD, encoding="utf-8"))
    text = to_toml(cfg)
    os.makedirs(os.path.dirname(NEW), exist_ok=True)
    with open(NEW, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"✅ 已迁移: {OLD}\n   → {NEW}")
    print(f"   大小: {len(text)} 字符")
    # 摘要（打码）
    for pname, pc in (cfg.get("providers") or {}).items():
        for k in pc.get("keys") or []:
            kv = k.get("key", "")
            disp = kv[:6] + "..." + kv[-6:] if kv else "(空)"
            print(f"   {k.get('id'):<12} {disp}  {k.get('note','')}")
    print(f"   targets: {[(t['name'], t['adapter']) for t in cfg.get('targets') or []]}")


if __name__ == "__main__":
    main()
