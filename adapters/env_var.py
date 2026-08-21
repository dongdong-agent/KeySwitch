#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 用户环境变量适配器（Hermes / DSH 共用 OPENCODE_GO_API_KEY）"""
import subprocess
import os
from .base import Adapter


class EnvVarAdapter(Adapter):
    name = "env_var"
    description = "Windows 用户环境变量（Hermes + DSH）"

    def __init__(self, env_name: str = "OPENCODE_GO_API_KEY", restart: list | None = None):
        self.env_name = env_name
        self._restart = restart or ["Hermes", "DSH"]

    def write_key(self, provider: str, key: str) -> dict:
        try:
            # PowerShell 设置 User 级环境变量
            ps = ("[Environment]::SetEnvironmentVariable('{0}','{1}','User')"
                  .format(self.env_name, key))
            r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                               capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return {"ok": False, "msg": f"环境变量设置失败: {r.stderr[:200]}"}
            return {"ok": True, "msg": f"环境变量 {self.env_name} 已更新 (需重启 Hermes/DSH 生效)"}
        except Exception as e:
            return {"ok": False, "msg": f"环境变量写入异常: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            r = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command",
                 f"[Environment]::GetEnvironmentVariable('{self.env_name}','User')"],
                capture_output=True, text=True, timeout=60)
            return r.stdout.strip()
        except Exception:
            return ""

    def restart_hint(self) -> list:
        return list(self._restart)


if __name__ == "__main__":
    a = EnvVarAdapter()
    print("当前用户环境变量 key 前8位:", a.read_key("opencode-go")[:8])
