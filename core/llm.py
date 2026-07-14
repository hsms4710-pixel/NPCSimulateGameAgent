"""LLM 客户端 — DeepSeek API 封装（异步安全）"""
import json, logging, os, asyncio
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "api_config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                cfg = json.load(f)
            self.api_key = cfg.get("api_key", "")
            self.api_base = cfg.get("api_base", "https://api.deepseek.com/v1")
            self.model = cfg.get("model", "deepseek-chat")
        else:
            self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            self.api_base = "https://api.deepseek.com/v1"
            self.model = "deepseek-chat"
        self.token_usage = {"sent": 0, "received": 0, "calls": 0}

    async def chat_async(self, messages: list, temperature: float = 0.8, max_tokens: int = 1024) -> str:
        """异步调用 — 放到线程池避免阻塞事件循环"""
        return await asyncio.to_thread(self.chat, messages, temperature, max_tokens)

    async def chat_json_async(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
        raw = await self.chat_async(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=temperature,
        )
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
        return {"raw": raw}

    def chat(self, messages: list, temperature: float = 0.8, max_tokens: int = 1024) -> str:
        if not self.api_key:
            return "(LLM未配置，使用默认回复)"
        try:
            resp = requests.post(
                f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            self.token_usage["sent"] += usage.get("prompt_tokens", 0)
            self.token_usage["received"] += usage.get("completion_tokens", 0)
            self.token_usage["calls"] += 1
            return content
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return f"(LLM调用失败: {e})"

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> dict:
        raw = self.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=temperature,
        )
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
        return {"raw": raw}
