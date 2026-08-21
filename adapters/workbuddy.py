#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy 适配器：~/.workbuddy/models.json

models.json 是模型数组，每项含 url / apiKey / model 等。
切换策略：把所有使用该 provider 端点(url 匹配 base_url 前缀)的模型项的 apiKey 替换。
"""
import json
import os
import time
from .base import Adapter

WB_FILE = os.path.expanduser(r"~/.workbuddy/models.json")

PROVIDER_URL_MAP = {
    "opencode-go": "opencode.ai/zen/go",
    "deepseek": "api.deepseek.com",
}


class WorkBuddyAdapter(Adapter):
    name = "workbuddy"
    description = "WorkBuddy (~/.workbuddy/models.json)"

    def write_key(self, provider: str, key: str) -> dict:
        url_mark = PROVIDER_URL_MAP.get(provider)
        if not url_mark:
            return {"ok": False, "msg": f"WorkBuddy 暂不支持 provider: {provider}"}
        try:
            path = WB_FILE
            if not os.path.exists(path):
                return {"ok": False, "msg": "WorkBuddy models.json 不存在"}
            with open(path, encoding="utf-8") as f:
                models = json.load(f)
            # 备份
            bak = f"{path}.bak-{time.strftime('%Y%m%d%H%M%S')}"
            with open(path, encoding="utf-8") as f:
                open(bak, "w", encoding="utf-8").write(f.read())
            changed = 0
            for m in models if isinstance(models, list) else models.get("models", []):
                url = str(m.get("url", ""))
                if url_mark in url:
                    m["apiKey"] = key
                    changed += 1
            if changed == 0:
                return {"ok": False, "msg": f"WorkBuddy 没有匹配 {provider} 的模型项"}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(models, f, ensure_ascii=False, indent=2)
            return {"ok": True, "msg": f"WorkBuddy: {changed} 个模型项 apiKey 已更新 (需重启 WorkBuddy)"}
        except Exception as e:
            return {"ok": False, "msg": f"WorkBuddy 写入失败: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            url_mark = PROVIDER_URL_MAP.get(provider)
            with open(WB_FILE, encoding="utf-8") as f:
                models = json.load(f)
            for m in models if isinstance(models, list) else models.get("models", []):
                if url_mark in str(m.get("url", "")) and m.get("apiKey"):
                    return m["apiKey"]
            return ""
        except Exception:
            return ""

    def restart_hint(self) -> list:
        return ["WorkBuddy"]


if __name__ == "__main__":
    a = WorkBuddyAdapter()
    print("WorkBuddy 当前 opencode-go key 前8位:", a.read_key("opencode-go")[:8])
