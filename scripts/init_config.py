#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 config/config.yaml：从现有位置自动收集 key（不经对话）

收集源：
  opencode-1: Windows 用户环境变量 OPENCODE_GO_API_KEY（Hermes 当前用）
  opencode-2: ~/.pi/agent/auth.json 的 opencode-go key
  opencode-3: 留空占位（用户自行补充）
  deepseek-1: ~/AppData/Roaming/OpenChatCut/.env.local 的 LLM_DEEPSEEK_API_KEY
"""
import json
import os
import subprocess
import sys
import yaml

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(APP_DIR, "config", "config.yaml")


def get_env_user(name: str) -> str:
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        f"[Environment]::GetEnvironmentVariable('{name}','User')"],
                       capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def read_json_key(path: str, provider: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get(provider, {}).get("key", "")
    except Exception:
        return ""


def read_env_local(name: str) -> str:
    try:
        with open(os.path.expanduser(r"~/AppData/Roaming/OpenChatCut/.env.local"), encoding="utf-8") as f:
            for line in f:
                if line.startswith(name + "="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return ""


def main():
    k1 = get_env_user("OPENCODE_GO_API_KEY")
    k2 = read_json_key(os.path.expanduser(r"~/.pi/agent/auth.json"), "opencode-go")
    k3 = ""
    kd = read_env_local("LLM_DEEPSEEK_API_KEY")

    cfg = {
        "thresholds": {
            "opencode-go": {"percent": 90},
            "deepseek": {"balance_min": 5},
        },
        "providers": {
            "opencode-go": {
                "base_url": "https://opencode.ai/zen/go/v1",
                "usage_type": "percent",
                "keys": [
                    {"id": "opencode-1", "key": k1, "note": "Hermes 在用"},
                    {"id": "opencode-2", "key": k2, "note": "pi 在用"},
                    {"id": "opencode-3", "key": k3, "note": "备用(待填)"},
                ],
            },
            "deepseek": {
                "base_url": "https://api.deepseek.com",
                "usage_type": "balance",
                "keys": [
                    {"id": "deepseek-1", "key": kd, "note": "官方充值"},
                ],
            },
        },
        "targets": [
            {"name": "pi", "adapter": "pi"},
            {"name": "hermes_dsh", "adapter": "env_var", "env": "OPENCODE_GO_API_KEY",
             "restart_hint": ["Hermes", "DSH"]},
            {"name": "openchatcut", "adapter": "openchatcut"},
            {"name": "workbuddy", "adapter": "workbuddy"},
        ],
        "active": {"provider": "opencode-go", "key_id": "opencode-1"},
    }

    with open(OUT, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    print("config.yaml 已生成:")
    print(f"  opencode-1: {k1[:8]}... (env) {'✅' if k1 else '❌ 空'}")
    print(f"  opencode-2: {k2[:8]}... (pi)  {'✅' if k2 else '❌ 空'}")
    print(f"  opencode-3: (待填)               ❌ 空")
    print(f"  deepseek-1: {kd[:8]}... (OpenChatCut) {'✅' if kd else '❌ 空'}")
    print(f"\n位置: {OUT}")
    print("提示: 打开文件补充 opencode-3 的 key，或直接改任何 key/note。")


if __name__ == "__main__":
    main()
