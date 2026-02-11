"""
Grok 视频生成服务
"""

import asyncio
from typing import AsyncGenerator, Optional

import orjson
from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import (
    UpstreamException,
    AppException,
    ValidationException,
    ErrorType,
)
from app.services.grok.models.model import ModelService
from app.services.token import get_token_manager, EffortType
from app.services.grok.processors import VideoStreamProcessor, VideoCollectProcessor
from app.services.grok.utils.headers import apply_statsig, build_sso_cookie
from app.services.grok.utils.stream import wrap_stream_with_usage

CREATE_POST_API = "https://grok.com/rest/media/post/create"
CHAT_API = "https://grok.com/rest/app-chat/conversations/new"

_MEDIA_SEMAPHORE = None
_MEDIA_SEM_VALUE = 0


def _get_semaphore() -> asyncio.Semaphore:
    """获取或更新信号量"""
    global _MEDIA_SEMAPHORE, _MEDIA_SEM_VALUE
    value = max(1, int(get_config("performance.media_max_concurrent")))
    if value != _MEDIA_SEM_VALUE:
        _MEDIA_SEM_VALUE = value
        _MEDIA_SEMAPHORE = asyncio.Semaphore(value)
    return _MEDIA_SEMAPHORE


class VideoService:
    """视频生成服务"""

    def __init__(self, proxy: str = None):
        self.proxy = proxy or get_config("network.base_proxy_url")
        self.timeout = get_config("network.timeout")

    def _build_headers(
        self, token: str, referer: str = "https://grok.com/imagine"
    ) -> dict:
        """构建请求头"""
        user_agent = get_config("security.user_agent")
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Baggage": "sentry-environment=production,sentry-release=d6add6fb0460641fd482d767a335ef72b9b6abb8,sentry-public_key=b311e0f2690c81f25e2c4cf6d4f7ce1c",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Origin": "https://grok.com",
            "Pragma": "no-cache",
            "Priority": "u=1, i",
            "Referer": referer,
            "Sec-Ch-Ua": '"Google Chrome";v="136", "Chromium";v="136", "Not(A:Brand";v="24"',
            "Sec-Ch-Ua-Arch": "arm",
            "Sec-Ch-Ua-Bitness": "64",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Model": "",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": user_agent,
        }

        apply_statsig(headers)
        headers["Cookie"] = build_sso_cookie(token)

        return headers

    def _build_proxies(self) -> Optional[dict]:
        """构建代理"""
        return {"http": self.proxy, "https": self.proxy} if self.proxy else None

    async def create_post(
        self,
        token: str,
        prompt: str,
        media_type: str = "MEDIA_POST_TYPE_VIDEO",
        media_url: str = None,
    ) -> str:
        """创建媒体帖子，返回 post ID"""
        try:
            headers = self._build_headers(token)

            # 根据类型构建不同的载荷
            if media_type == "MEDIA_POST_TYPE_IMAGE" and media_url:
                payload = {"mediaType": media_type, "mediaUrl": media_url}
            else:
                payload = {"mediaType": media_type, "prompt": prompt}

            async with AsyncSession() as session:
                response = await session.post(
                    CREATE_POST_API,
                    headers=headers,
                    json=payload,
                    impersonate=get_config("security.browser"),
                    timeout=30,
                    proxies=self._build_proxies(),
                )

            if response.status_code != 200:
                logger.error(f"Create post failed: {response.status_code}")
                raise UpstreamException(
                    f"Failed to create post: {response.status_code}"
                )

            post_id = response.json().get("post", {}).get("id", "")
            if not post_id:
                raise UpstreamException("No post ID in response")

            logger.info(f"Media post created: {post_id} (type={media_type})")
            return post_id

        except AppException:
            raise
        except Exception as e:
            logger.error(f"Create post error: {e}")
            raise UpstreamException(f"Create post error: {str(e)}")

    async def create_image_post(self, token: str, image_url: str) -> str:
        """创建图片帖子，返回 post ID"""
        return await self.create_post(
            token, prompt="", media_type="MEDIA_POST_TYPE_IMAGE", media_url=image_url
        )

    def _build_payload(
        self,
        prompt: str,
        post_id: str,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution_name: str = "480p",
        preset: str = "normal",
    ) -> dict:
        """构建视频生成载荷"""
        mode_map = {
            "fun": "--mode=extremely-crazy",
            "normal": "--mode=normal",
            "spicy": "--mode=extremely-spicy-or-crazy",
        }
        mode_flag = mode_map.get(preset, "--mode=custom")

        payload = {
            "temporary": True,
            "modelName": "grok-3",
            "message": f"{prompt} {mode_flag}",
            "toolOverrides": {"videoGen": True},
            "enableSideBySide": True,
            "deviceEnvInfo": {
                "darkModeEnabled": False,
                "devicePixelRatio": 2,
                "screenWidth": 1920,
                "screenHeight": 1080,
                "viewportWidth": 1920,
                "viewportHeight": 1080,
            },
            "responseMetadata": {
                "experiments": [],
                "modelConfigOverride": {
                    "modelMap": {
                        "videoGenModelConfig": {
                            "aspectRatio": aspect_ratio,
                            "parentPostId": post_id,
                            "resolutionName": resolution_name,
                            "videoLength": video_length,
                        }
                    }
                },
            },
        }

        logger.debug(f"Video generation payload: {payload}")

        return payload

    async def _generate_internal(
        self,
        token: str,
        post_id: str,
        prompt: str,
        aspect_ratio: str,
        video_length: int,
        resolution_name: str,
        preset: str,
    ) -> AsyncGenerator[bytes, None]:
        """内部生成逻辑"""
        session = None
        try:
            headers = self._build_headers(token)
            payload = self._build_payload(
                prompt, post_id, aspect_ratio, video_length, resolution_name, preset
            )

            session = AsyncSession(impersonate=get_config("security.browser"))
            response = await session.post(
                CHAT_API,
                headers=headers,
                data=orjson.dumps(payload),
                timeout=self.timeout,
                stream=True,
                proxies=self._build_proxies(),
            )

            if response.status_code != 200:
                logger.error(
                    f"Video generation failed: status={response.status_code}, post_id={post_id}"
                )
                raise UpstreamException(
                    message=f"Video generation failed: {response.status_code}",
                    details={"status": response.status_code},
                )

            logger.info(f"Video generation started: post_id={post_id}")

            async def stream_response():
                try:
                    async for line in response.aiter_lines():
                        yield line
                finally:
                    await session.close()

            return stream_response()

        except Exception as e:
            if session:
                try:
                    await session.close()
                except Exception:
                    pass
            logger.error(f"Video generation error: {e}")
            if isinstance(e, AppException):
                raise
            raise UpstreamException(f"Video generation error: {str(e)}")

    async def generate(
        self,
        token: str,
        prompt: str,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution_name: str = "480p",
        preset: str = "normal",
    ) -> AsyncGenerator[bytes, None]:
        """生成视频"""
        logger.info(
            f"Video generation: prompt='{prompt[:50]}...', ratio={aspect_ratio}, length={video_length}s, preset={preset}"
        )
        async with _get_semaphore():
            post_id = await self.create_post(token, prompt)
            return await self._generate_internal(
                token,
                post_id,
                prompt,
                aspect_ratio,
                video_length,
                resolution_name,
                preset,
            )

    async def generate_from_image(
        self,
        token: str,
        prompt: str,
        image_url: str,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution: str = "480p",
        preset: str = "normal",
    ) -> AsyncGenerator[bytes, None]:
        """从图片生成视频"""
        logger.info(
            f"Image to video: prompt='{prompt[:50]}...', image={image_url[:80]}"
        )
        async with _get_semaphore():
            post_id = await self.create_image_post(token, image_url)
            return await self._generate_internal(
                token, post_id, prompt, aspect_ratio, video_length, resolution, preset
            )

    @staticmethod
    async def completions(
        model: str,
        messages: list,
        stream: bool = None,
        thinking: str = None,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution: str = "480p",
        preset: str = "normal",
    ):
        """视频生成入口"""
        # 获取 token（使用智能路由）
        token_mgr = await get_token_manager()
        await token_mgr.reload_if_stale()

        # 使用智能路由选择 token（根据视频需求与候选池）
        pool_candidates = ModelService.pool_candidates_for_model(model)
        token_info = token_mgr.get_token_for_video(
            resolution=resolution,
            video_length=video_length,
            pool_candidates=pool_candidates,
        )

        if not token_info:
            raise AppException(
                message="No available tokens. Please try again later.",
                error_type=ErrorType.RATE_LIMIT.value,
                code="rate_limit_exceeded",
                status_code=429,
            )

        # 从 TokenInfo 对象中提取 token 字符串
        token = token_info.token
        if token.startswith("sso="):
            token = token[4:]

        think = {"enabled": True, "disabled": False}.get(thinking)
        is_stream = stream if stream is not None else get_config("chat.stream")

        # 提取内容
        from app.services.grok.services.chat import MessageExtractor
        from app.services.grok.services.assets import UploadService

        try:
            prompt, attachments = MessageExtractor.extract(messages, is_video=True)
        except ValueError as e:
            raise ValidationException(str(e))

        # 处理图片附件 - 支持token轮换重试
        image_url = None
        if attachments:
            upload_service = UploadService()
            max_token_retries = 3  # 最多尝试3个不同的token
            current_token = token

            try:
                for attach_type, attach_data in attachments:
                    if attach_type == "image":
                        uploaded = False
                        last_error = None

                        # 尝试上传图片，如果遇到403则轮换token重试
                        for retry_idx in range(max_token_retries):
                            try:
                                _, file_uri = await upload_service.upload(attach_data, current_token)
                                image_url = f"https://assets.grok.com/{file_uri}"
                                uploaded = True
                                logger.info(
                                    f"Image uploaded for video: {image_url} "
                                    f"(token尝试次数: {retry_idx + 1})"
                                )
                                break
                            except Exception as e:
                                last_error = e
                                # 检查是否为403认证错误
                                is_403_error = False
                                if hasattr(e, 'details') and isinstance(e.details, dict):
                                    if e.details.get('status') == 403:
                                        is_403_error = True
                                elif '403' in str(e):
                                    is_403_error = True

                                if is_403_error and retry_idx < max_token_retries - 1:
                                    logger.warning(
                                        f"视频图片上传遇到403错误 (尝试 {retry_idx + 1}/{max_token_retries})，"
                                        f"尝试轮换token重试..."
                                    )
                                    # 获取新的token
                                    try:
                                        new_token = None
                                        for pool_name in ModelService.pool_candidates_for_model(model):
                                            new_token = token_mgr.get_token(pool_name)
                                            if new_token and new_token != current_token:
                                                break
                                        if new_token and new_token != current_token:
                                            current_token = new_token
                                            logger.info(f"已切换到新token: {current_token[:10]}...")
                                        else:
                                            logger.warning("没有可用的其他token，使用相同token重试")
                                    except Exception as token_err:
                                        logger.error(f"获取新token失败: {token_err}")
                                        raise last_error
                                else:
                                    # 非403错误或已达到最大重试次数
                                    raise

                        if not uploaded and last_error:
                            logger.error(f"视频图片上传失败，已尝试 {max_token_retries} 个token")
                            raise last_error
                        break
            finally:
                await upload_service.close()

            # 更新token以便后续video生成使用最新的有效token
            token = current_token

        # 生成视频
        service = VideoService()
        if image_url:
            response = await service.generate_from_image(
                token, prompt, image_url, aspect_ratio, video_length, resolution, preset
            )
        else:
            response = await service.generate(
                token, prompt, aspect_ratio, video_length, resolution, preset
            )

        # 处理响应
        if is_stream:
            processor = VideoStreamProcessor(model, token, think)
            return wrap_stream_with_usage(
                processor.process(response), token_mgr, token, model
            )

        result = await VideoCollectProcessor(model, token).process(response)
        try:
            model_info = ModelService.get(model)
            effort = (
                EffortType.HIGH
                if (model_info and model_info.cost.value == "high")
                else EffortType.LOW
            )
            await token_mgr.consume(token, effort)
            logger.debug(f"Video completed, recorded usage (effort={effort.value})")
        except Exception as e:
            logger.warning(f"Failed to record video usage: {e}")
        return result


__all__ = ["VideoService"]
