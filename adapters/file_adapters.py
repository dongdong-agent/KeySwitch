#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用声明式适配器：新增软件多数只需在 config.yaml 声明，无需写代码

三种通用型：
  file_json   : JSON 文件 + 点路径（config.json 里 {"opencode-go": {"key": ...}}
                → key_path: opencode-go.key；列表下标支持 [0]）
  file_env    : KEY=VALUE 文本文件（.env 类）
  file_regex  : 正则替换兜底（pattern 必须含 1 个捕获组用于读取）

config.yaml 用法示例：
  - name: my_app
    label: 我的软件
    adapter: file_json
    path: C:/xx/config.json
    key_path: opencode-go.key
    mapping:
      opencode-go: opencode-1
"""
import json
import os
import re
import shutil
import time
from .base import Adapter


def _backup(path: str):
    if os.path.exists(path):
        bak = path + f".bak-{time.strftime('%Y%m%d%H%M%S')}"
        try:
            shutil.copy2(path, bak)
        except Exception:
            pass


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


class JsonFileAdapter(Adapter):
    name = "file_json"
    description = "通用 JSON 文件（点路径定位 key 字段）"

    def __init__(self, path: str = "", key_path: str = "api_key"):
        self.path = path
        self.key_path = key_path

    @staticmethod
    def _walk(d, parts):
        cur = d
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            elif isinstance(cur, list):
                try:
                    cur = cur[int(p)]
                except Exception:
                    return None
            else:
                return None
        return cur

    @staticmethod
    def _set(d, parts, val):
        cur = d
        for p in parts[:-1]:
            if isinstance(cur, dict):
                cur = cur.setdefault(p, {})
            elif isinstance(cur, list):
                idx = int(p)
                while len(cur) <= idx:
                    cur.append({})
                cur = cur[idx]
        last = parts[-1]
        if isinstance(cur, dict):
            cur[last] = val
        elif isinstance(cur, list):
            idx = int(last)
            while len(cur) <= idx:
                cur.append(None)
            cur[idx] = val

    def write_key(self, provider: str, key: str) -> dict:
        try:
            _backup(self.path)
            d = json.loads(_read_text(self.path))
            self._set(d, self.key_path.split("."), key)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
            return {"ok": True, "msg": f"JSON {os.path.basename(self.path)} 已更新"}
        except Exception as e:
            return {"ok": False, "msg": f"写入失败: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            d = json.loads(_read_text(self.path))
            v = self._walk(d, self.key_path.split("."))
            return v if isinstance(v, str) else ""
        except Exception:
            return ""


class EnvFileAdapter(Adapter):
    name = "file_env"
    description = "通用 KEY=VALUE 文件（.env 类）"

    def __init__(self, path: str = "", key_name: str = "API_KEY"):
        self.path = path
        self.key_name = key_name

    def write_key(self, provider: str, key: str) -> dict:
        try:
            _backup(self.path)
            lines = []
            if os.path.exists(self.path):
                lines = _read_text(self.path).splitlines()
            found = False
            for i, ln in enumerate(lines):
                if ln.strip().startswith(self.key_name + "="):
                    lines[i] = f"{self.key_name}={key}"
                    found = True
            if not found:
                lines.append(f"{self.key_name}={key}")
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return {"ok": True, "msg": f"{os.path.basename(self.path)} 已更新"}
        except Exception as e:
            return {"ok": False, "msg": f"写入失败: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            for ln in _read_text(self.path).splitlines():
                if ln.strip().startswith(self.key_name + "="):
                    return ln.split("=", 1)[1].strip()
        except Exception:
            pass
        return ""


class RegexFileAdapter(Adapter):
    name = "file_regex"
    description = "通用正则替换（pattern 含 1 个捕获组）"

    def __init__(self, path: str = "", pattern: str = "",
                 replacement: str = "\\1{key}\\2"):
        self.path = path
        self.pattern = pattern
        self.replacement = replacement

    def write_key(self, provider: str, key: str) -> dict:
        try:
            _backup(self.path)
            text = _read_text(self.path)
            new = re.sub(self.pattern, self.replacement.format(key=key), text)
            if new == text:
                return {"ok": False, "msg": "正则未匹配到任何内容"}
            with open(self.path, "w", encoding="utf-8") as f:
                f.write(new)
            return {"ok": True, "msg": f"{os.path.basename(self.path)} 已更新"}
        except Exception as e:
            return {"ok": False, "msg": f"写入失败: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            m = re.search(self.pattern, _read_text(self.path))
            if m and m.lastindex and m.lastindex >= 1:
                return m.group(1)
        except Exception:
            pass
        return ""
