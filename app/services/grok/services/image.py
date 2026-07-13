"""
Grok image service.

Image generation now prefers app-chat REST + imageGen overrides and
falls back to the legacy Imagine WebSocket path when needed.
"""

import asyncio
import certifi
import json
import orjson
import re
import ssl
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from aiohttp_socks import ProxyConnector

from app.core.config import get_config
from app.core.exceptions import UpstreamException
from app.core.logger import logger
from app.services.grok.processors import (
    ImageCollectProcessor,
    ImageStreamProcessor,
    ImageWSCollectProcessor,
    ImageWSStreamProcessor,
)
from app.services.grok.processors.base import _normalize_stream_line
from app.services.grok.services.chat import GrokChatService
from app.services.grok.utils.headers import build_grok_ws_headers
from app.services.grok.utils.urls import grok_ws_url

WS_URL = "/ws/imagine/listen"
CHAT_NEW_API = "/rest/app-chat/conversations/new"
CHAT_RESPONSES_API = "/rest/app-chat/conversations/{conversation_id}/responses"


class _BlockedError(Exception):
    pass


class ImageService:
    """Grok image service."""

    def __init__(self):
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.load_verify_locations(certifi.where())
        self._url_pattern = re.compile(r"/images/([a-f0-9-]+)\.(png|jpg|jpeg)")

    def _resolve_proxy(self) -> tuple[aiohttp.BaseConnector, Optional[str]]:
        proxy_url = get_config("network.base_proxy_url")
        if not proxy_url:
            return aiohttp.TCPConnector(ssl=self._ssl_context), None

        scheme = urlparse(proxy_url).scheme.lower()
        if scheme.startswith("socks"):
            logger.info(f"Using SOCKS proxy: {proxy_url}")
            return ProxyConnector.from_url(proxy_url, ssl=self._ssl_context), None

        logger.info(f"Using HTTP proxy: {proxy_url}")
        return aiohttp.TCPConnector(ssl=self._ssl_context), proxy_url

    def _get_ws_headers(self, token: str) -> Dict[str, str]:
        return build_grok_ws_headers(token)

    def _extract_image_id(self, url: str) -> Optional[str]:
        match = self._url_pattern.search(url or "")
        return match.group(1) if match else None

    def _is_final_image(self, url: str, blob_size: int) -> bool:
        return (url or "").lower().endswith(
            (".jpg", ".jpeg")
        ) and blob_size > get_config("image.image_ws_final_min_bytes")

    def _classify_image(self, url: str, blob: str) -> Optional[Dict[str, object]]:
        if not url or not blob:
            return None

        image_id = self._extract_image_id(url) or uuid.uuid4().hex
        blob_size = len(blob)
        is_final = self._is_final_image(url, blob_size)

        stage = (
            "final"
            if is_final
            else (
                "medium"
                if blob_size > get_config("image.image_ws_medium_min_bytes")
                else "preview"
            )
        )

        return {
            "type": "image",
            "image_id": image_id,
            "stage": stage,
            "blob": blob,
            "blob_size": blob_size,
            "url": url,
            "is_final": is_final,
        }

    def _build_app_chat_overrides(
        self,
        model_info,
        n: int,
        enable_nsfw: bool,
    ) -> Dict[str, Any]:
        """Build request overrides that force image generation via app-chat."""
        return {
            "enableImageGeneration": True,
            "returnImageBytes": False,
            "returnRawGrokInXaiRequest": False,
            "enableImageStreaming": True,
            "imageGenerationCount": n,
            "forceConcise": False,
            "toolOverrides": {"imageGen": True},
            "enableSideBySide": True,
            "sendFinalMetadata": True,
            "isReasoning": False,
            "disableTextFollowUps": False,
            "enableNsfw": enable_nsfw,
            "forceSideBySide": False,
            "responseMetadata": {
                "modelConfigOverride": {"modelMap": {}},
                "requestModelDetails": {"modelId": model_info.model_id},
            },
        }

    def _build_browser_image_payload(
        self,
        prompt: str,
        parent_response_id: str,
        n: int,
        enable_nsfw: bool,
        mode_id: str,
    ) -> Dict[str, Any]:
        """Build a browser-like /responses payload based on the web client."""
        return {
            "message": prompt,
            "parentResponseId": parent_response_id,
            "disableSearch": False,
            "enableImageGeneration": True,
            "imageAttachments": [],
            "returnImageBytes": False,
            "returnRawGrokInXaiRequest": False,
            "fileAttachments": [],
            "enableImageStreaming": True,
            "imageGenerationCount": n,
            "forceConcise": False,
            "toolOverrides": {
                "gmailSearch": False,
                "googleCalendarSearch": False,
                "outlookSearch": False,
                "outlookCalendarSearch": False,
                "googleDriveSearch": False,
            },
            "enableSideBySide": True,
            "sendFinalMetadata": True,
            "metadata": {"request_metadata": {}},
            "disableTextFollowUps": False,
            "isFromGrokFiles": False,
            "disableMemory": bool(get_config("chat.disable_memory")),
            "forceSideBySide": False,
            "isAsyncChat": False,
            "skipCancelCurrentInflightRequests": False,
            "isRegenRequest": False,
            "disableSelfHarmShortCircuit": False,
            "collectionIds": [],
            "connectors": [],
            "searchAllConnectors": False,
            "deviceEnvInfo": {
                "darkModeEnabled": False,
                "devicePixelRatio": 1,
                "screenWidth": 2560,
                "screenHeight": 1440,
                "viewportWidth": 2388,
                "viewportHeight": 564,
            },
            "modeId": mode_id,
            "enable420": bool(enable_nsfw),
        }

    def _image_mode_id(self, model_info) -> str:
        """Infer web modeId from the configured image model."""
        model_mode = str(getattr(model_info, "model_mode", "") or "").upper()
        cost = getattr(getattr(model_info, "cost", None), "value", "")
        if "EXPERT" in model_mode or cost == "high":
            return "expert"
        if "FAST" in model_mode or "MINI" in model_mode:
            return "fast"
        return "regular"

    def _extract_stream_context(self, payload: Dict[str, Any]) -> tuple[str, str]:
        """Best-effort extraction of conversation_id and response_id from stream payloads."""

        def _walk(value: Any) -> tuple[str, str]:
            conversation_id = ""
            response_id = ""

            if isinstance(value, dict):
                conversation_id = str(
                    value.get("conversationId")
                    or value.get("conversation_id")
                    or ""
                )
                response_id = str(
                    value.get("responseId") or value.get("response_id") or ""
                )
                if conversation_id and response_id:
                    return conversation_id, response_id

                if (
                    not conversation_id
                    and isinstance(value.get("conversation"), dict)
                    and value["conversation"].get("id")
                ):
                    conversation_id = str(value["conversation"]["id"])

                for item in value.values():
                    found_conversation_id, found_response_id = _walk(item)
                    if not conversation_id and found_conversation_id:
                        conversation_id = found_conversation_id
                    if not response_id and found_response_id:
                        response_id = found_response_id
                    if conversation_id and response_id:
                        return conversation_id, response_id

            elif isinstance(value, list):
                for item in value:
                    found_conversation_id, found_response_id = _walk(item)
                    if found_conversation_id or found_response_id:
                        return found_conversation_id, found_response_id

            return conversation_id, response_id

        return _walk(payload)

    async def _bootstrap_conversation(
        self,
        token: str,
        model_info,
    ) -> tuple[str, str]:
        """Create a lightweight app-chat conversation and capture its context IDs."""
        chat_service = GrokChatService()
        bootstrap_payload = {
            "temporary": False,
            "modelName": model_info.grok_model,
            "message": "Reply with OK only.",
            "fileAttachments": [],
            "imageAttachments": [],
            "disableSearch": True,
            "enableImageGeneration": False,
            "returnImageBytes": False,
            "enableImageStreaming": False,
            "imageGenerationCount": 1,
            "forceConcise": True,
            "toolOverrides": {},
            "enableSideBySide": True,
            "sendFinalMetadata": True,
            "responseMetadata": {
                "modelConfigOverride": {"modelMap": {}},
                "requestModelDetails": {"modelId": model_info.model_id},
            },
            "disableMemory": bool(get_config("chat.disable_memory")),
            "deviceEnvInfo": {
                "darkModeEnabled": False,
                "devicePixelRatio": 1,
                "screenWidth": 2560,
                "screenHeight": 1440,
                "viewportWidth": 2388,
                "viewportHeight": 564,
            },
        }
        if getattr(model_info, "model_mode", None):
            bootstrap_payload["modelMode"] = model_info.model_mode

        stream = await chat_service.chat(
            token=token,
            message="Reply with OK only.",
            model=model_info.grok_model,
            mode=model_info.model_mode,
            stream=True,
            raw_payload=bootstrap_payload,
            path=CHAT_NEW_API,
            referer="https://grok.com/",
        )

        conversation_id = ""
        user_response_id = ""
        response_id = ""
        async for line in stream:
            line = _normalize_stream_line(line)
            if not line:
                continue
            try:
                data = orjson.loads(line)
            except orjson.JSONDecodeError:
                continue

            resp = data.get("result", {}).get("response", {})
            found_conversation_id, found_response_id = self._extract_stream_context(data)
            if not conversation_id and found_conversation_id:
                conversation_id = found_conversation_id
            if (
                isinstance(resp.get("userResponse"), dict)
                and resp["userResponse"].get("responseId")
            ):
                user_response_id = str(resp["userResponse"]["responseId"])
            if (
                isinstance(resp.get("modelResponse"), dict)
                and resp["modelResponse"].get("responseId")
            ):
                response_id = str(resp["modelResponse"]["responseId"])
            elif found_response_id and found_response_id != user_response_id:
                response_id = found_response_id

            if conversation_id and response_id:
                logger.info(
                    f"Image app-chat bootstrap ready: conversation_id={conversation_id}, response_id={response_id}"
                )
                return conversation_id, response_id

        raise UpstreamException(
            message="Failed to bootstrap app-chat conversation context",
            details={
                "type": "bootstrap_failed",
                "model": model_info.model_id,
                "conversation_id": conversation_id,
                "user_response_id": user_response_id,
            },
        )

    def _ws_fallback_enabled(self) -> bool:
        return bool(get_config("image.image_ws"))

    def _prefer_final_image_urls(self, images: List[str]) -> List[str]:
        """Collapse preview/final URL pairs and prefer the final image URL."""
        grouped: Dict[str, str] = {}
        ordered: List[str] = []

        for image in images:
            if not isinstance(image, str) or not image:
                continue
            canonical = re.sub(r"-part-\d+(?=/image\.[a-zA-Z0-9]+$)", "", image)
            if canonical not in grouped:
                ordered.append(canonical)
                grouped[canonical] = image
                continue
            current = grouped[canonical]
            current_is_partial = "-part-" in current
            incoming_is_partial = "-part-" in image
            if current_is_partial and not incoming_is_partial:
                grouped[canonical] = image

        return [grouped[key] for key in ordered]

    async def _stream_app_chat(
        self,
        token: str,
        prompt: str,
        model_info,
        n: int = 1,
        response_format: str = "b64_json",
        enable_nsfw: bool = True,
        size: str = "1024x1024",
    ) -> AsyncGenerator[str, None]:
        """Stream images through app-chat REST using imageGen override."""
        conversation_id, parent_response_id = await self._bootstrap_conversation(
            token, model_info
        )
        mode_id = self._image_mode_id(model_info)
        chat_service = GrokChatService()
        response = await chat_service.chat(
            token=token,
            message=prompt,
            model=model_info.grok_model,
            mode=model_info.model_mode,
            stream=True,
            raw_payload=self._build_browser_image_payload(
                prompt=prompt,
                parent_response_id=parent_response_id,
                n=n,
                enable_nsfw=enable_nsfw,
                mode_id=mode_id,
            ),
            path=CHAT_RESPONSES_API.format(conversation_id=conversation_id),
            referer=f"https://grok.com/c/{conversation_id}?rid={parent_response_id}",
        )
        processor = ImageStreamProcessor(
            model_info.model_id,
            token,
            n=n,
            response_format=response_format,
        )
        return processor.process(response)

    async def _collect_app_chat(
        self,
        token: str,
        prompt: str,
        model_info,
        n: int = 1,
        response_format: str = "b64_json",
        enable_nsfw: bool = True,
    ) -> List[str]:
        """Collect images through app-chat REST using imageGen override."""
        conversation_id, parent_response_id = await self._bootstrap_conversation(
            token, model_info
        )
        mode_id = self._image_mode_id(model_info)
        chat_service = GrokChatService()
        response = await chat_service.chat(
            token=token,
            message=prompt,
            model=model_info.grok_model,
            mode=model_info.model_mode,
            stream=True,
            raw_payload=self._build_browser_image_payload(
                prompt=prompt,
                parent_response_id=parent_response_id,
                n=n,
                enable_nsfw=enable_nsfw,
                mode_id=mode_id,
            ),
            path=CHAT_RESPONSES_API.format(conversation_id=conversation_id),
            referer=f"https://grok.com/c/{conversation_id}?rid={parent_response_id}",
        )
        processor = ImageCollectProcessor(
            model_info.model_id,
            token,
            response_format=response_format,
        )
        images = await processor.process(response)
        if response_format == "url":
            images = self._prefer_final_image_urls(images)
        if images:
            return images
        raise UpstreamException(
            message="app-chat image generation returned empty data",
            details={
                "type": "empty_image",
                "path": "app_chat",
                "model": model_info.model_id,
                "prompt_preview": prompt[:80],
            },
        )

    def _stream_ws(
        self,
        token: str,
        prompt: str,
        model_info,
        aspect_ratio: str = "2:3",
        n: int = 1,
        response_format: str = "b64_json",
        enable_nsfw: bool = True,
        size: str = "1024x1024",
    ) -> AsyncGenerator[str, None]:
        """Stream images via the legacy Imagine WebSocket path."""
        upstream = self.stream(
            token=token,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            n=n,
            enable_nsfw=enable_nsfw,
        )
        processor = ImageWSStreamProcessor(
            model_info.model_id,
            token,
            n=n,
            response_format=response_format,
            size=size,
        )
        return processor.process(upstream)

    async def _collect_ws(
        self,
        token: str,
        prompt: str,
        model_info,
        aspect_ratio: str = "2:3",
        n: int = 1,
        response_format: str = "b64_json",
        enable_nsfw: bool = True,
    ) -> List[str]:
        """Collect images via the legacy Imagine WebSocket path."""
        upstream = self.stream(
            token=token,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            n=n,
            enable_nsfw=enable_nsfw,
        )
        processor = ImageWSCollectProcessor(
            model_info.model_id,
            token,
            n=n,
            response_format=response_format,
        )
        return await processor.process(upstream)

    async def stream_generate(
        self,
        token: str,
        prompt: str,
        model_info,
        aspect_ratio: str = "2:3",
        n: int = 1,
        response_format: str = "b64_json",
        enable_nsfw: bool = True,
        size: str = "1024x1024",
    ) -> AsyncGenerator[str, None]:
        """Prefer app-chat streaming and fall back to ws_imagine on failure."""

        async def _runner():
            try:
                logger.info("Image stream: trying app-chat imageGen path first")
                app_chat_stream = await self._stream_app_chat(
                    token=token,
                    prompt=prompt,
                    model_info=model_info,
                    n=n,
                    response_format=response_format,
                    enable_nsfw=enable_nsfw,
                    size=size,
                )
                async for chunk in app_chat_stream:
                    yield chunk
                return
            except Exception as e:
                logger.warning(
                    f"Image stream app-chat failed, falling back to ws_imagine: {e}"
                )
                if not self._ws_fallback_enabled():
                    raise

            async for chunk in self._stream_ws(
                token=token,
                prompt=prompt,
                model_info=model_info,
                aspect_ratio=aspect_ratio,
                n=n,
                response_format=response_format,
                enable_nsfw=enable_nsfw,
                size=size,
            ):
                yield chunk

        return _runner()

    async def generate(
        self,
        token: str,
        prompt: str,
        model_info,
        aspect_ratio: str = "2:3",
        n: int = 1,
        response_format: str = "b64_json",
        enable_nsfw: bool = True,
    ) -> List[str]:
        """Prefer app-chat collection and fall back to ws_imagine on failure."""
        try:
            logger.info("Image generation: trying app-chat imageGen path first")
            return await self._collect_app_chat(
                token=token,
                prompt=prompt,
                model_info=model_info,
                n=n,
                response_format=response_format,
                enable_nsfw=enable_nsfw,
            )
        except Exception as e:
            logger.warning(
                f"Image generation app-chat failed, falling back to ws_imagine: {e}"
            )
            if not self._ws_fallback_enabled():
                raise
            return await self._collect_ws(
                token=token,
                prompt=prompt,
                model_info=model_info,
                aspect_ratio=aspect_ratio,
                n=n,
                response_format=response_format,
                enable_nsfw=enable_nsfw,
            )

    async def stream(
        self,
        token: str,
        prompt: str,
        aspect_ratio: str = "2:3",
        n: int = 1,
        enable_nsfw: bool = True,
        max_retries: int = None,
    ) -> AsyncGenerator[Dict[str, object], None]:
        retries = max(1, max_retries if max_retries is not None else 1)
        logger.info(
            f"Image generation: prompt='{prompt[:50]}...', n={n}, ratio={aspect_ratio}, nsfw={enable_nsfw}"
        )

        for attempt in range(retries):
            try:
                yielded_any = False
                async for item in self._stream_once(
                    token, prompt, aspect_ratio, n, enable_nsfw
                ):
                    yielded_any = True
                    yield item
                return
            except _BlockedError:
                if yielded_any or attempt + 1 >= retries:
                    if not yielded_any:
                        yield {
                            "type": "error",
                            "error_code": "blocked",
                            "error": "blocked_no_final_image",
                        }
                    return
                logger.warning(f"WebSocket blocked, retry {attempt + 1}/{retries}")
            except Exception as e:
                logger.error(f"WebSocket stream failed: {e}")
                return

    async def _stream_once(
        self,
        token: str,
        prompt: str,
        aspect_ratio: str,
        n: int,
        enable_nsfw: bool,
    ) -> AsyncGenerator[Dict[str, object], None]:
        request_id = str(uuid.uuid4())
        headers = self._get_ws_headers(token)
        timeout = float(get_config("network.timeout"))
        blocked_seconds = float(get_config("image.image_ws_blocked_seconds"))

        try:
            connector, proxy = self._resolve_proxy()
        except Exception as e:
            logger.error(f"WebSocket proxy setup failed: {e}")
            return

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.ws_connect(
                    grok_ws_url(WS_URL),
                    headers=headers,
                    heartbeat=20,
                    receive_timeout=timeout,
                    proxy=proxy,
                ) as ws:
                    message = {
                        "type": "conversation.item.create",
                        "timestamp": int(time.time() * 1000),
                        "item": {
                            "type": "message",
                            "content": [
                                {
                                    "requestId": request_id,
                                    "text": prompt,
                                    "type": "input_text",
                                    "properties": {
                                        "section_count": 0,
                                        "is_kids_mode": False,
                                        "enable_nsfw": enable_nsfw,
                                        "skip_upsampler": False,
                                        "is_initial": False,
                                        "aspect_ratio": aspect_ratio,
                                    },
                                }
                            ],
                        },
                    }

                    await ws.send_json(message)
                    logger.info(f"WebSocket request sent: {prompt[:80]}...")

                    images = {}
                    completed = 0
                    start_time = last_activity = time.time()
                    medium_received_time = None

                    while time.time() - start_time < timeout:
                        try:
                            ws_msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                        except asyncio.TimeoutError:
                            if (
                                medium_received_time
                                and completed == 0
                                and time.time() - medium_received_time
                                > min(10, blocked_seconds)
                            ):
                                raise _BlockedError()
                            if completed > 0 and time.time() - last_activity > 10:
                                logger.info(
                                    f"WebSocket idle timeout, collected {completed} images"
                                )
                                break
                            continue

                        if ws_msg.type == aiohttp.WSMsgType.TEXT:
                            last_activity = time.time()
                            msg = json.loads(ws_msg.data)
                            msg_type = msg.get("type")

                            if msg_type == "image":
                                info = self._classify_image(
                                    msg.get("url", ""), msg.get("blob", "")
                                )
                                if not info:
                                    continue

                                image_id = info["image_id"]
                                existing = images.get(image_id, {})

                                if (
                                    info["stage"] == "medium"
                                    and medium_received_time is None
                                ):
                                    medium_received_time = time.time()

                                if info["is_final"] and not existing.get("is_final"):
                                    completed += 1
                                    logger.debug(
                                        f"Final image received: id={image_id}, size={info['blob_size']}"
                                    )

                                images[image_id] = {
                                    "is_final": info["is_final"]
                                    or existing.get("is_final")
                                }
                                yield info

                            elif msg_type == "error":
                                logger.warning(
                                    f"WebSocket error: {msg.get('err_code', '')} - {msg.get('err_msg', '')}"
                                )
                                yield {
                                    "type": "error",
                                    "error_code": msg.get("err_code", ""),
                                    "error": msg.get("err_msg", ""),
                                }
                                return

                            if completed >= n:
                                logger.info(
                                    f"WebSocket collected {completed} final images"
                                )
                                break

                            if (
                                medium_received_time
                                and completed == 0
                                and time.time() - medium_received_time > blocked_seconds
                            ):
                                raise _BlockedError()

                        elif ws_msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            logger.warning(f"WebSocket closed/error: {ws_msg.type}")
                            yield {
                                "type": "error",
                                "error_code": "ws_closed",
                                "error": f"websocket closed: {ws_msg.type}",
                            }
                            break

        except aiohttp.WSServerHandshakeError as e:
            ws_url = e.request_info.real_url if e.request_info else grok_ws_url(WS_URL)
            logger.error(
                f"WebSocket handshake failed: status={e.status}, message={e.message}, url={ws_url}"
            )
            error_code = (
                "unauthorized"
                if e.status in (401, 403)
                else f"handshake_http_{e.status}"
            )
            yield {
                "type": "error",
                "error_code": error_code,
                "error": f"websocket handshake failed: HTTP {e.status}",
            }
        except aiohttp.ClientError as e:
            logger.error(f"WebSocket connection error: {e}")
            yield {"type": "error", "error_code": "connection_failed", "error": str(e)}


image_service = ImageService()

__all__ = ["image_service", "ImageService"]
