#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""切换 opencode-go key：pi + Hermes 环境变量 + KeySwitch 配置池（opencode-1 槽位）

用法：python tools/switch_opencode_key.py <新key>
"""
import json
import os
import subprocess
import sys

NEW_KEY = sys.argv[1].strip()


def mask(k: str) -> str:
    return k[:6] + "..." + k[-6:] if len(k) > 12 else "(短)"


def main():
    results = []

    # 1) pi auth.json
    pi_path = os.path.expanduser(r"~/.pi/agent/auth.json")
    d = json.load(open(pi_path, encoding="utf-8"))
    old_pi = d.get("opencode-go", {}).get("key", "")
    d["opencode-go"] = {"type": "api_key", "key": NEW_KEY}
    with open(pi_path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    results.append(f"pi: {mask(old_pi)} → {mask(NEW_KEY)}")

    # 2) Hermes 用户环境变量
    old_env = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         "[Environment]::GetEnvironmentVariable('OPENCODE_GO_API_KEY','User')"],
        capture_output=True, text=True, timeout=60).stdout.strip()
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         f"[Environment]::SetEnvironmentVariable('OPENCODE_GO_API_KEY','{NEW_KEY}','User')"],
        check=True, timeout=60)
    results.append(f"Hermes 环境变量: {mask(old_env)} → {mask(NEW_KEY)}")

    # 3) KeySwitch Rust 版 TOML（opencode-1 槽位）
    toml_path = os.path.join(os.environ.get("APPDATA", ""), "KeySwitch", "config.toml")
    if os.path.exists(toml_path):
        t = open(toml_path, encoding="utf-8").read()
        t = t.replace('id = "opencode-1"\nkey = "', 'id = "opencode-1"\nkey = "')  # noop 占位
        # 精确定位 opencode-1 的 key 行替换
        lines = t.splitlines()
        for i, ln in enumerate(lines):
            if ln == 'id = "opencode-1"':
                for j in range(i + 1, min(i + 3, len(lines))):
                    if lines[j].startswith("key = "):
                        lines[j] = f'key = "{NEW_KEY}"'
                        break
        open(toml_path, "w", encoding="utf-8").write("\n".join(lines))
        results.append("KeySwitch TOML: opencode-1 已更新")

    # 4) KeySwitch Python 版 yaml（同步）
    yaml_path = r"L:\00-projects\apikey-switcher\config\config.yaml"
    if os.path.exists(yaml_path):
        import yaml as _y
        c = _y.safe_load(open(yaml_path, encoding="utf-8"))
        for k in c["providers"]["opencode-go"]["keys"]:
            if k["id"] == "opencode-1":
                k["key"] = NEW_KEY
        with open(yaml_path, "w", encoding="utf-8") as f:
            _y.safe_dump(c, f, allow_unicode=True, sort_keys=False)
        results.append("KeySwitch YAML: opencode-1 已更新")

    print("\n".join(results))
    print(f"\n✅ 切换完成: {mask(NEW_KEY)}")


if __name__ == "__main__":
    main()
