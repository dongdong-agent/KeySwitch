#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenChatCut 适配器：~/AppData/Roaming/OpenChatCut/.env.local

OpenChatCut 的 LLM 配置格式：
  LLM_PROVIDER=<provider>
  LLM_<PROVIDER>_API_KEY=<key>
  LLM_<PROVIDER>_BASE_URL=<可选，覆盖默认端点>

provider 映射：
  opencode-go → LLM_PROVIDER=deepseek + LLM_DEEPSEEK_API_KEY + LLM_DEEPSEEK_BASE_URL=https://opencode.ai/zen/go/v1
  deepseek     → LLM_PROVIDER=deepseek + LLM_DEEPSEEK_API_KEY + （清掉 BASE_URL 用官方默认）
"""
import os
import time
from .base import Adapter

ENV_LOCAL = os.path.expanduser(r"~/AppData/Roaming/OpenChatCut/.env.local")

PROVIDER_MAP = {
    # provider: (LLM_PROVIDER 值, 环境变量后缀, 覆盖 base_url 或 None)
    "opencode-go": ("deepseek", "DEEPSEEK", "https://opencode.ai/zen/go/v1"),
    "deepseek": ("deepseek", "DEEPSEEK", None),
}


class OpenChatCutAdapter(Adapter):
    name = "openchatcut"
    description = "OpenChatCut (~/AppData/Roaming/OpenChatCut/.env.local)"

    def write_key(self, provider: str, key: str) -> dict:
        if provider not in PROVIDER_MAP:
            return {"ok": False, "msg": f"OpenChatCut 暂不支持 provider: {provider}"}
        llm_provider, suffix, base_url = PROVIDER_MAP[provider]
        try:
            path = ENV_LOCAL
            lines = []
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            # 备份
            bak = f"{path}.bak-{time.strftime('%Y%m%d%H%M%S')}"
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    open(bak, "w", encoding="utf-8").write(f.read())
            # 重建：LLM_PROVIDER + LLM_<SUF>_API_KEY + (BASE_URL)
            out = []
            replaced_provider = False
            replaced_key = False
            replaced_base = False
            for line in lines:
                if line.startswith("LLM_PROVIDER="):
                    out.append(f"LLM_PROVIDER={llm_provider}")
                    replaced_provider = True
                elif line.startswith(f"LLM_{suffix}_API_KEY="):
                    out.append(f"LLM_{suffix}_API_KEY={key}")
                    replaced_key = True
                elif line.startswith(f"LLM_{suffix}_BASE_URL="):
                    if base_url:
                        out.append(f"LLM_{suffix}_BASE_URL={base_url}")
                        replaced_base = True
                    # base_url 为 None 时不保留该行（用官方默认）
                else:
                    out.append(line)
            if not replaced_provider:
                out.append(f"LLM_PROVIDER={llm_provider}")
            if not replaced_key:
                out.append(f"LLM_{suffix}_API_KEY={key}")
            if base_url and not replaced_base:
                out.append(f"LLM_{suffix}_BASE_URL={base_url}")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(out) + "\n")
            return {"ok": True, "msg": f"OpenChatCut: LLM_{suffix}_API_KEY 已更新 (重启生效)"}
        except Exception as e:
            return {"ok": False, "msg": f"OpenChatCut 写入失败: {e}"}

    def read_key(self, provider: str) -> str:
        try:
            if provider not in PROVIDER_MAP:
                return ""
            _, suffix, _ = PROVIDER_MAP[provider]
            with open(ENV_LOCAL, encoding="utf-8") as f:
                for line in f:
                    if line.startswith(f"LLM_{suffix}_API_KEY="):
                        return line.strip().split("=", 1)[1]
            return ""
        except Exception:
            return ""

    def restart_hint(self) -> list:
        return ["OpenChatCut"]


if __name__ == "__main__":
    a = OpenChatCutAdapter()
    print("OpenChatCut 当前 deepseek key 前8位:", a.read_key("deepseek")[:8])
