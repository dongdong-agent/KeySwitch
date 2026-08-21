#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""适配器基类：每个目标软件一个适配器，负责把激活的 key 写入对应位置"""

class Adapter:
    name = "base"
    description = ""

    def write_key(self, provider: str, key: str) -> dict:
        """写入 key 到本软件配置。返回 {ok: bool, msg: str}"""
        raise NotImplementedError

    def read_key(self, provider: str) -> str:
        """读取当前配置的 key（用于状态展示，可返回空）"""
        return ""

    def restart_hint(self) -> list:
        """切换后需要重启的软件名列表"""
        return []
