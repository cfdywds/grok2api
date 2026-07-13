"""
LM Studio 客户端封装

通过 OpenAI 兼容 API 调用 LM Studio 本地部署的大模型
使用 aiohttp（项目已有依赖）
"""

from typing import AsyncGenerator, List, Dict, Optional

import aiohttp
import orjson

from app.core.config import get_config
from app.core.logger import logger


class LMStudioClient:
    """LM Studio OpenAI 兼容 API 客户端"""

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def base_url(self) -> str:
        return get_config("copilot.lmstudio_base_url", "http://localhost:1234/v1")

    @property
    def model(self) -> str:
        return get_config("copilot.lmstudio_model", "")

    @property
    def timeout(self) -> int:
        return get_config("copilot.lmstudio_timeout", 60)

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                json_serialize=lambda x: orjson.dumps(x).decode(),
            )
        return self._session

    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
    ) -> str:
        """
        非流式调用 LM Studio，返回 assistant 回复文本

        Args:
            messages: OpenAI 格式消息列表
            temperature: 采样温度

        Returns:
            assistant 回复文本
        """
        session = self._get_session()
        url = f"{self.base_url}/chat/completions"

        payload = {
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if self.model:
            payload["model"] = self.model

        try:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data["choices"][0]["message"]["content"]
        except aiohttp.ClientConnectorError:
            logger.error("LMStudioClient: 无法连接到 LM Studio，请确认服务已启动")
            raise ConnectionError(
                f"无法连接到 LM Studio ({self.base_url})，请确认服务已启动"
            )
        except Exception as e:
            logger.error(f"LMStudioClient: 调用失败: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        流式调用 LM Studio，逐 token yield

        Args:
            messages: OpenAI 格式消息列表
            temperature: 采样温度

        Yields:
            每个 token 的文本内容
        """
        session = self._get_session()
        url = f"{self.base_url}/chat/completions"

        payload = {
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if self.model:
            payload["model"] = self.model

        try:
            async with session.post(url, json=payload) as response:
                response.raise_for_status()
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = orjson.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue
        except aiohttp.ClientConnectorError:
            logger.error("LMStudioClient: 无法连接到 LM Studio，请确认服务已启动")
            raise ConnectionError(
                f"无法连接到 LM Studio ({self.base_url})，请确认服务已启动"
            )
        except Exception as e:
            logger.error(f"LMStudioClient: 流式调用失败: {e}")
            raise

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
