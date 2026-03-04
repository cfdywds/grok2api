"""
Grok 视频生成服务

支持:
- 文本/图片生成视频
- 视频延长 (extend)
- 从已有 parent post 生成
- 内容审核自动重试
- Token 轮换重试 (429)
- 智能提示词判别
- 视频超分辨率 (upscale)
"""

import asyncio
import re
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
from app.services.grok.utils.headers import build_grok_headers, build_sso_cookie
from app.services.grok.utils.stream import wrap_stream_with_usage
from app.services.grok.processors.base import _normalize_stream_line

CREATE_POST_API = "https://grok.com/rest/media/post/create"
CHAT_API = "https://grok.com/rest/app-chat/conversations/new"

# CJK 字符回避指令（追加到视频 prompt，减少画面内中文乱码）
_CJK_AVOIDANCE_SUFFIX = (
    "(IMPORTANT: All text visible in the video must use English/Latin characters only. "
    "Never render Chinese/Japanese/Korean characters as visible text in the video.)"
)

_CJK_RANGE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff"
    r"\uac00-\ud7af\uf900-\ufaff]"
)

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


def _token_tag(token: str) -> str:
    """Token 脱敏标记（日志用）"""
    raw = token[4:] if token.startswith("sso=") else token
    if not raw:
        return "empty"
    if len(raw) <= 14:
        return raw
    return f"{raw[:6]}...{raw[-6:]}"


def _classify_video_error(exc: Exception) -> tuple[str, str, int]:
    """将底层异常归一化为用户可读错误。

    Returns:
        (message, code, status_code)
    """
    text = str(exc or "").lower()
    details = getattr(exc, "details", None)
    body = ""
    if isinstance(details, dict):
        body = str(details.get("body") or "").lower()
    merged = f"{text}\n{body}"

    if (
        "upload authentication failed" in merged
        or "upload auth failed" in merged
    ):
        return ("视频生成失败：图片上传被拒绝（403），请配置代理后重试", "upload_auth_failed", 502)

    if (
        "blocked by moderation" in merged
        or "content moderated" in merged
        or "content-moderated" in merged
        or '"code":3' in merged
        or "'code': 3" in merged
    ):
        return ("视频生成被拒绝，请调整提示词或素材后重试", "video_rejected", 400)

    if (
        "tls connect error" in merged
        or "timed out" in merged
        or "timeout" in merged
        or "connection closed" in merged
        or "http/2" in merged
        or "curl: (35)" in merged
        or "network" in merged
        or "proxy" in merged
    ):
        return ("视频生成失败：网络连接异常，请稍后重试", "video_network_error", 502)

    return ("视频生成失败，请稍后重试", "video_failed", 502)


def _is_rate_limited(exc: Exception) -> bool:
    """检查异常是否为 429 限流"""
    if isinstance(exc, UpstreamException):
        details = getattr(exc, "details", None)
        if isinstance(details, dict) and details.get("status") == 429:
            return True
    if isinstance(exc, AppException) and exc.status_code == 429:
        return True
    return "429" in str(exc)


class VideoService:
    """视频生成服务"""

    def __init__(self, proxy: str = None):
        self.proxy = proxy or get_config("network.base_proxy_url")
        self.timeout = get_config("network.timeout")

    # ==================== 智能提示词 ====================

    @staticmethod
    def is_meaningful_video_prompt(prompt: str) -> bool:
        """判断提示词是否属于"有效自定义视频提示词"。

        以下场景视为非自定义（返回 False）：
        - 空提示词
        - 仅"让它动起来/生成视频/animate this"等泛化短提示
        """
        text = (prompt or "").strip().lower()
        if not text:
            return False

        text = re.sub(r"\s+", " ", text).strip(
            " \t\r\n.,!?;:，。！？；：'\"`~()[]{}<>《》「」【】"
        )
        key = re.sub(r"\s+", "", text)
        if not text:
            return False

        generic_en = {
            "animate", "animate this", "animate this image",
            "make it move", "make this move",
            "generate video", "make video", "make a video",
            "create video", "turn this into a video",
            "turn it into a video", "video",
        }
        generic_zh = {
            "动起来", "让它动起来", "让图片动起来", "让这张图动起来",
            "生成视频", "生成一个视频", "生成一段视频",
            "做成视频", "做个视频", "制作视频",
            "变成视频", "变成一个视频", "视频",
        }
        if text in generic_en or key in generic_zh:
            return False

        if re.fullmatch(r"(please\s+)?animate(\s+this(\s+image)?)?", text):
            return False
        if re.fullmatch(
            r"(please\s+)?(make|create|generate)\s+(a\s+)?video", text
        ):
            return False
        if re.fullmatch(
            r"(请|请你|帮我|麻烦你)?(把)?(它|图片|这张图)?"
            r"(动起来|生成视频|做成视频|制作视频)(吧|一下|下)?",
            key,
        ):
            return False

        return True

    @staticmethod
    def _map_preset_to_mode(preset: str) -> str:
        """将前端预设名映射为 Grok 官方 mode 参数。"""
        mapping = {
            "spicy": "extremely-spicy-or-crazy",
            "fun": "extremely-crazy",
            "normal": "normal",
        }
        return mapping.get(preset, "extremely-spicy-or-crazy")

    @staticmethod
    def _build_video_message(
        prompt: str,
        preset: str = "normal",
        source_image_url: str = "",
    ) -> str:
        """构造视频请求 message：
        - 有提示词：统一走 custom，并发送 image_url + prompt + mode
        - 无提示词：根据所选 preset 转换 mode
        - CJK 回避：检测到中日韩字符时追加英文渲染指令
        """
        prompt_text = (prompt or "").strip()
        if not VideoService.is_meaningful_video_prompt(prompt_text):
            prompt_text = ""

        # 检测 CJK 字符 → 追加回避指令
        avoid_cjk = bool(get_config("video.avoid_cjk_text", True))
        if avoid_cjk and prompt_text and _CJK_RANGE.search(prompt_text):
            prompt_text = f"{prompt_text} {_CJK_AVOIDANCE_SUFFIX}"

        image_core = (source_image_url or "").strip()
        if prompt_text:
            mode_flag = "--mode=custom"
            if image_core:
                return f"{image_core}  {prompt_text} {mode_flag}"
            return f"{prompt_text} {mode_flag}"

        official_mode = VideoService._map_preset_to_mode(preset)
        mode_flag = f"--mode={official_mode}"
        if image_core:
            return f"{image_core}  {mode_flag}"
        return mode_flag

    # ==================== 审核检测 ====================

    @staticmethod
    def _is_moderated_line(line) -> bool:
        """检测流式行是否包含审核拦截标记"""
        text = _normalize_stream_line(line)
        if not text:
            return False
        try:
            data = orjson.loads(text)
        except Exception:
            return False
        resp = data.get("result", {}).get("response", {})
        video_resp = resp.get("streamingVideoGenerationResponse", {})
        return bool(video_resp.get("moderated") is True)

    @staticmethod
    def _build_imagine_public_url(parent_post_id: str) -> str:
        return f"https://imagine-public.x.ai/imagine-public/images/{parent_post_id}.jpg"

    # ==================== 请求构造 ====================

    def _build_headers(
        self, token: str, referer: str = "https://grok.com/imagine", include_rw: bool = False
    ) -> dict:
        """构建请求头"""
        headers = build_grok_headers(token)
        headers["Referer"] = referer
        if include_rw:
            # 写操作需要 sso-rw cookie 授权（同 assets.py 的上传/删除逻辑）
            headers["Cookie"] = build_sso_cookie(token, include_rw=True)
        return headers

    def _build_proxies(self) -> Optional[dict]:
        """构建代理"""
        return {"http": self.proxy, "https": self.proxy} if self.proxy else None

    # ==================== Media Post ====================

    async def create_post(
        self,
        token: str,
        prompt: str,
        media_type: str = "MEDIA_POST_TYPE_VIDEO",
        media_url: str = None,
    ) -> str:
        """创建媒体帖子，返回 post ID"""
        try:
            # create_post 是写操作，需要 sso-rw cookie
            headers = self._build_headers(token, include_rw=True)

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
                try:
                    resp_body = response.text[:300]
                except Exception:
                    resp_body = "<unreadable>"
                logger.error(
                    f"Create post failed: {response.status_code} | body={resp_body}"
                )
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
            msg, code, status = _classify_video_error(e)
            raise AppException(
                message=msg,
                error_type=ErrorType.SERVER.value if status >= 500 else ErrorType.INVALID_REQUEST.value,
                code=code,
                status_code=status,
            )

    async def create_image_post(self, token: str, image_url: str) -> str:
        """创建图片帖子，返回 post ID"""
        return await self.create_post(
            token, prompt="", media_type="MEDIA_POST_TYPE_IMAGE", media_url=image_url
        )

    # ==================== 生成逻辑 ====================

    async def _stream_with_moderation_retry(
        self,
        token: str,
        message: str,
        model_config_override: dict,
        official_mode: str,
        post_id: str,
    ) -> AsyncGenerator[bytes, None]:
        """带审核重试的流式生成内部方法"""
        moderated_max_retry = max(1, int(get_config("video.moderated_max_retry", 5)))
        token_tag = _token_tag(token)

        async def _stream():
            for attempt in range(1, moderated_max_retry + 1):
                session = AsyncSession(impersonate=get_config("security.browser"))
                moderated_hit = False
                try:
                    headers = self._build_headers(token)
                    payload = {
                        "temporary": True,
                        "modelName": "grok-3",
                        "message": message,
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
                            "modelConfigOverride": model_config_override,
                        },
                    }

                    response = await session.post(
                        CHAT_API,
                        headers=headers,
                        data=orjson.dumps(payload),
                        timeout=self.timeout,
                        stream=True,
                        proxies=self._build_proxies(),
                    )

                    if response.status_code != 200:
                        raise UpstreamException(
                            message=f"Video generation failed: {response.status_code}",
                            details={"status": response.status_code},
                        )

                    logger.info(
                        f"Video generation started: token={token_tag}, post_id={post_id}, "
                        f"attempt={attempt}/{moderated_max_retry}"
                    )

                    async for line in response.aiter_lines():
                        if self._is_moderated_line(line):
                            moderated_hit = True
                            logger.warning(
                                f"Video generation moderated: token={token_tag}, "
                                f"retry {attempt}/{moderated_max_retry}"
                            )
                            break
                        yield line

                    if not moderated_hit:
                        return
                    if attempt < moderated_max_retry:
                        await asyncio.sleep(1.2)
                        continue
                    raise UpstreamException(
                        "Video blocked by moderation",
                        details={"moderated": True, "attempts": moderated_max_retry},
                    )
                except Exception as e:
                    if isinstance(e, AppException):
                        raise
                    msg, code, status = _classify_video_error(e)
                    raise AppException(
                        message=msg,
                        error_type=ErrorType.SERVER.value if status >= 500 else ErrorType.INVALID_REQUEST.value,
                        code=code,
                        status_code=status,
                    )
                finally:
                    try:
                        await session.close()
                    except Exception:
                        pass

        return _stream()

    async def generate(
        self,
        token: str,
        prompt: str,
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution_name: str = "480p",
        preset: str = "normal",
    ) -> AsyncGenerator[bytes, None]:
        """生成视频（带审核重试）"""
        token_tag = _token_tag(token)
        is_custom = self.is_meaningful_video_prompt(prompt)
        official_mode = "custom" if is_custom else self._map_preset_to_mode(preset)

        logger.info(
            f"Video generation: token={token_tag}, prompt='{prompt[:50]}...', "
            f"ratio={aspect_ratio}, length={video_length}s, mode={official_mode}"
        )

        async with _get_semaphore():
            post_id = await self.create_post(token, prompt)
            message = self._build_video_message(prompt=prompt, preset=preset)
            model_config_override = {
                "modelMap": {
                    "videoGenModelConfig": {
                        "mode": official_mode,
                        "aspectRatio": aspect_ratio,
                        "parentPostId": post_id,
                        "resolutionName": resolution_name,
                        "videoLength": video_length,
                        "isVideoEdit": False,
                    }
                }
            }
            logger.debug(
                f"Video generate config: videoLength={video_length}, "
                f"mode={official_mode}, ratio={aspect_ratio}, res={resolution_name}"
            )
            return await self._stream_with_moderation_retry(
                token, message, model_config_override, official_mode, post_id
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
        """从图片生成视频（带审核重试）"""
        token_tag = _token_tag(token)
        is_custom = self.is_meaningful_video_prompt(prompt)
        official_mode = "custom" if is_custom else self._map_preset_to_mode(preset)

        logger.info(
            f"Image to video: token={token_tag}, prompt='{prompt[:50]}...', "
            f"image={image_url[:80]}, mode={official_mode}"
        )

        async with _get_semaphore():
            post_id = await self.create_image_post(token, image_url)
            # 用 imagine-public.x.ai 格式的 URL 作为消息里的图片引用
            # assets.grok.com URL 是文件附件系统，Grok 视频 AI 不认识，会触发误审核
            # imagine-public.x.ai 是 Grok 自己的图片系统，视频 AI 能正确识别
            imagine_url = self._build_imagine_public_url(post_id)
            message = self._build_video_message(
                prompt=prompt, preset=preset, source_image_url=imagine_url,
            )
            model_config_override = {
                "modelMap": {
                    "videoGenModelConfig": {
                        "mode": official_mode,
                        "aspectRatio": aspect_ratio,
                        "parentPostId": post_id,
                        "resolutionName": resolution,
                        "videoLength": video_length,
                        "isVideoEdit": False,
                    }
                }
            }
            logger.debug(
                f"Image-to-video config: videoLength={video_length}, "
                f"mode={official_mode}, ratio={aspect_ratio}, res={resolution}"
            )
            return await self._stream_with_moderation_retry(
                token, message, model_config_override, official_mode, post_id
            )

    async def generate_from_parent_post(
        self,
        token: str,
        prompt: str,
        parent_post_id: str,
        source_image_url: str = "",
        aspect_ratio: str = "3:2",
        video_length: int = 6,
        resolution: str = "480p",
        preset: str = "normal",
    ) -> AsyncGenerator[bytes, None]:
        """从已有 parent post ID 生成视频"""
        token_tag = _token_tag(token)
        is_custom = self.is_meaningful_video_prompt(prompt)
        official_mode = "custom" if is_custom else self._map_preset_to_mode(preset)

        logger.info(
            f"ParentPost to video: token={token_tag}, prompt='{prompt[:50]}...', "
            f"parent_post_id={parent_post_id}"
        )

        source_image_url = self._build_imagine_public_url(parent_post_id)

        # 对齐官网全链路：先创建 IMAGE 类型 media post
        try:
            await self.create_image_post(token, source_image_url)
        except Exception as e:
            logger.warning(
                f"ParentPost pre-create media post failed, continue anyway: "
                f"parent_post_id={parent_post_id}, error={e}"
            )

        message = self._build_video_message(
            prompt=prompt, preset=preset, source_image_url=source_image_url,
        )
        model_config_override = {
            "modelMap": {
                "videoGenModelConfig": {
                    "mode": official_mode,
                    "aspectRatio": aspect_ratio,
                    "parentPostId": parent_post_id,
                    "resolutionName": resolution,
                    "videoLength": video_length,
                    "isVideoEdit": False,
                }
            }
        }

        return await self._stream_with_moderation_retry(
            token, message, model_config_override, official_mode, parent_post_id
        )

    async def generate_extend_video(
        self,
        token: str,
        prompt: str,
        extend_post_id: str,
        video_extension_start_time: float,
        original_post_id: str = "",
        file_attachment_id: str = "",
        aspect_ratio: str = "16:9",
        video_length: int = 6,
        resolution: str = "480p",
        preset: str = "normal",
        stitch_with_extend: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        """通过 Grok 官方视频延长 API 延长视频。"""
        token_tag = _token_tag(token)
        prompt_text = (prompt or "").strip()
        is_custom = self.is_meaningful_video_prompt(prompt_text)
        if is_custom:
            mode = "custom"
        else:
            mode = self._map_preset_to_mode(preset)
            prompt_text = ""

        # CJK 回避
        avoid_cjk = bool(get_config("video.avoid_cjk_text", True))
        if avoid_cjk and prompt_text and _CJK_RANGE.search(prompt_text):
            prompt_text = f"{prompt_text} {_CJK_AVOIDANCE_SUFFIX}"

        effective_original = (original_post_id or "").strip() or extend_post_id
        effective_file_attachment = (file_attachment_id or "").strip() or effective_original

        logger.info(
            f"Video extension request: token={token_tag}, extend_post_id={extend_post_id}, "
            f"start_time={video_extension_start_time}, original_post_id={effective_original}, "
            f"prompt='{(prompt_text or '')[:50]}', mode={mode}"
        )

        if prompt_text:
            message = f"{prompt_text} --mode={mode}"
        else:
            message = f"--mode={mode}"

        video_gen_config = {
            "isVideoExtension": True,
            "videoExtensionStartTime": video_extension_start_time,
            "extendPostId": extend_post_id,
            "stitchWithExtendPostId": stitch_with_extend,
            "originalPostId": effective_original,
            "originalRefType": "ORIGINAL_REF_TYPE_VIDEO_EXTENSION",
            "mode": mode,
            "aspectRatio": aspect_ratio,
            "videoLength": video_length,
            "resolutionName": resolution,
            "parentPostId": extend_post_id,
            "isVideoEdit": False,
        }
        if prompt_text:
            video_gen_config["originalPrompt"] = prompt_text

        model_config_override = {
            "modelMap": {"videoGenModelConfig": video_gen_config}
        }

        moderated_max_retry = max(1, int(get_config("video.moderated_max_retry", 5)))
        file_attachments = [effective_file_attachment]

        async def _stream():
            for attempt in range(1, moderated_max_retry + 1):
                session = AsyncSession(impersonate=get_config("security.browser"))
                moderated_hit = False
                try:
                    headers = self._build_headers(token)
                    payload = {
                        "temporary": True,
                        "modelName": "grok-3",
                        "message": message,
                        "fileAttachments": file_attachments,
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
                            "modelConfigOverride": model_config_override,
                        },
                    }

                    response = await session.post(
                        CHAT_API,
                        headers=headers,
                        data=orjson.dumps(payload),
                        timeout=self.timeout,
                        stream=True,
                        proxies=self._build_proxies(),
                    )

                    if response.status_code != 200:
                        raise UpstreamException(
                            message=f"Video extension failed: {response.status_code}",
                            details={"status": response.status_code},
                        )

                    logger.info(
                        f"Video extension started: token={token_tag}, extend_post_id={extend_post_id}, "
                        f"attempt={attempt}/{moderated_max_retry}"
                    )

                    async for line in response.aiter_lines():
                        if self._is_moderated_line(line):
                            moderated_hit = True
                            logger.warning(
                                f"Video extension moderated: token={token_tag}, "
                                f"retry {attempt}/{moderated_max_retry}"
                            )
                            break
                        yield line

                    if not moderated_hit:
                        return
                    if attempt < moderated_max_retry:
                        await asyncio.sleep(1.2)
                        continue
                    raise UpstreamException(
                        "Video extension blocked by moderation",
                        details={"moderated": True, "attempts": moderated_max_retry},
                    )
                except Exception as e:
                    if isinstance(e, AppException):
                        raise
                    msg, code, status = _classify_video_error(e)
                    raise AppException(
                        message=msg,
                        error_type=ErrorType.SERVER.value if status >= 500 else ErrorType.INVALID_REQUEST.value,
                        code=code,
                        status_code=status,
                    )
                finally:
                    try:
                        await session.close()
                    except Exception:
                        pass

        return _stream()

    # ==================== 入口方法 ====================

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
        parent_post_id: str | None = None,
        extend_post_id: str | None = None,
        video_extension_start_time: float | None = None,
        original_post_id: str | None = None,
        file_attachment_id: str | None = None,
        stitch_with_extend: bool = True,
        source_image_url: str | None = None,
    ):
        """视频生成入口（支持 token 轮换重试）"""
        token_mgr = await get_token_manager()
        await token_mgr.reload_if_stale()

        max_token_retries = int(get_config("retry.max_retry"))
        last_error: Exception | None = None

        think = {"enabled": True, "disabled": False}.get(thinking)
        is_stream = stream if stream is not None else get_config("chat.stream")
        should_upscale = bool(get_config("video.auto_upscale", True))

        # 提取内容
        from app.services.grok.services.chat import MessageExtractor
        from app.services.grok.services.assets import UploadService

        try:
            prompt, attachments = MessageExtractor.extract(messages, is_video=True)
        except ValueError as e:
            raise ValidationException(str(e))

        parent_post_id = (parent_post_id or "").strip() or None
        source_image_url = (source_image_url or "").strip()

        # 从 AssetTokenMap 获取绑定的 token
        from app.services.grok.utils.asset_token_map import AssetTokenMap

        token_map = AssetTokenMap.get_instance()
        preferred_token = ""
        if extend_post_id:
            preferred_token = token_map.get_token(extend_post_id) or ""
        elif parent_post_id:
            preferred_token = token_map.get_token(parent_post_id) or ""
        if preferred_token.startswith("sso="):
            preferred_token = preferred_token[4:]

        used_tokens: set[str] = set()

        for attempt in range(max_token_retries):
            token = ""

            # 优先使用绑定的 token
            if preferred_token and preferred_token not in used_tokens:
                token = preferred_token
                logger.info(f"Video token routing: preferred bound token -> token={_token_tag(token)}")

            if not token:
                pool_candidates = ModelService.pool_candidates_for_model(model)
                token_info = token_mgr.get_token_for_video(
                    resolution=resolution,
                    video_length=video_length,
                    pool_candidates=pool_candidates,
                )

                if not token_info:
                    if last_error:
                        raise last_error
                    raise AppException(
                        message="No available tokens. Please try again later.",
                        error_type=ErrorType.RATE_LIMIT.value,
                        code="rate_limit_exceeded",
                        status_code=429,
                    )

                token = token_info.token
                if token.startswith("sso="):
                    token = token[4:]

            used_tokens.add(token)

            try:
                # 处理图片附件
                image_url = None
                if (not parent_post_id) and attachments:
                    upload_service = UploadService()
                    try:
                        for attach_type, attach_data in attachments:
                            if attach_type == "image":
                                _, file_uri = await upload_service.upload(attach_data, token)
                                # file_uri 可能是完整 URL 或相对路径，防御性处理
                                if file_uri.startswith("http"):
                                    image_url = file_uri
                                else:
                                    image_url = f"https://assets.grok.com/{file_uri.lstrip('/')}"
                                logger.info(f"Image uploaded for video: {image_url} (file_uri={file_uri})")
                                break
                    finally:
                        await upload_service.close()

                # 生成视频
                service = VideoService()
                if extend_post_id and video_extension_start_time is not None:
                    response = await service.generate_extend_video(
                        token=token,
                        prompt=prompt,
                        extend_post_id=extend_post_id,
                        video_extension_start_time=video_extension_start_time,
                        original_post_id=original_post_id or "",
                        file_attachment_id=file_attachment_id or "",
                        aspect_ratio=aspect_ratio,
                        video_length=video_length,
                        resolution=resolution,
                        preset=preset,
                        stitch_with_extend=stitch_with_extend,
                    )
                elif parent_post_id:
                    response = await service.generate_from_parent_post(
                        token=token,
                        prompt=prompt,
                        parent_post_id=parent_post_id,
                        source_image_url=source_image_url,
                        aspect_ratio=aspect_ratio,
                        video_length=video_length,
                        resolution=resolution,
                        preset=preset,
                    )
                elif image_url:
                    response = await service.generate_from_image(
                        token, prompt, image_url, aspect_ratio, video_length, resolution, preset
                    )
                else:
                    response = await service.generate(
                        token, prompt, aspect_ratio, video_length, resolution, preset
                    )

                # 处理响应
                if is_stream:
                    processor = VideoStreamProcessor(
                        model, token, think,
                        upscale_on_finish=should_upscale,
                    )
                    return wrap_stream_with_usage(
                        processor.process(response), token_mgr, token, model
                    )

                result = await VideoCollectProcessor(
                    model, token,
                    upscale_on_finish=should_upscale,
                ).process(response)
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

            except UpstreamException as e:
                last_error = e
                if _is_rate_limited(e):
                    await token_mgr.mark_rate_limited(token)
                    logger.warning(
                        f"Token {_token_tag(token)} rate limited (429), "
                        f"trying next token (attempt {attempt + 1}/{max_token_retries})"
                    )
                    continue
                msg, code, status = _classify_video_error(e)
                raise AppException(
                    message=msg,
                    error_type=ErrorType.SERVER.value if status >= 500 else ErrorType.INVALID_REQUEST.value,
                    code=code,
                    status_code=status,
                )

        if last_error:
            raise last_error
        raise AppException(
            message="No available tokens. Please try again later.",
            error_type=ErrorType.RATE_LIMIT.value,
            code="rate_limit_exceeded",
            status_code=429,
        )


__all__ = ["VideoService"]
