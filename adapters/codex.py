#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex (codex-router) 适配器：~/.codex/codex-router/*.secret 文件

codex-router 的 API forwarder 从 protected file 读 key（health 里
credential_source 显示 protected file）。opencode-go 系列 4 个 provider
（opencode-go / -messages / -responses / opencode-zen）共用同一个
opencode-go-api-key.secret 文件，写一个即全部生效。
"""
import os
import time
from .base import Adapter

CODEX_STATE = os.path.expanduser(r"~/.codex/codex-router")


class CodexAdapter(Adapter):
    name = "codex"
    description = "Codex (codex-router secret 文件)"

    SECRET_MAP = {
        "opencode-go": "opencode-go-api-key.secret",
        "deepseek": "deepseek-api-key.secret",
    }

    def _secret_path(self, provider: str) -> str:
        fname = self.SECRET_MAP.get(provider, f"{provider}-api-key.secret")
        return os.path.join(CODEX_STATE, fname)

    def write_key(self, provider: str, key: str) -> dict:
        path = self._secret_path(provider)
        try:
            if os.path.exists(path):
                bak = path + f".bak-{time.strftime('%Y%m%d%H%M%S')}"
                os.replace(path, bak)
            with open(path, "w", encoding="utf-8") as f:
                f.write(key)
            return {"ok": True, "msg": f"已写 {os.path.basename(path)}（重启 Codex CLI 生效）"}
        except Exception as e:
            return {"ok": False, "msg": f"写入失败: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            with open(self._secret_path(provider), encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return ""

    def restart_hint(self) -> list:
        return ["Codex CLI"]
