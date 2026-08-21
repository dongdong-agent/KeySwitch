#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pi 工具适配器：~/.pi/agent/auth.json"""
import json
import os
import time
from .base import Adapter

PI_AUTH = os.path.expanduser(r"~/.pi/agent/auth.json")


class PiAdapter(Adapter):
    name = "pi"
    description = "pi 工具 (~/.pi/agent/auth.json)"

    def write_key(self, provider: str, key: str) -> dict:
        try:
            path = PI_AUTH
            data = {}
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            # 备份
            bak = f"{path}.bak-{time.strftime('%Y%m%d%H%M%S')}"
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    open(bak, "w", encoding="utf-8").write(f.read())
            # 只更新该 provider 的 key（其他 provider 保留）
            data.setdefault(provider, {})["type"] = "api_key"
            data[provider]["key"] = key
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            return {"ok": True, "msg": f"pi: {provider} key 已写入 (备份 {os.path.basename(bak)})"}
        except Exception as e:
            return {"ok": False, "msg": f"pi 写入失败: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            with open(PI_AUTH, encoding="utf-8") as f:
                return json.load(f).get(provider, {}).get("key", "")
        except Exception:
            return ""


if __name__ == "__main__":
    # 自测
    import sys
    a = PiAdapter()
    print("读取当前 key 前8位:", a.read_key("opencode-go")[:8])
