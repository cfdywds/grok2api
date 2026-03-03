"""
视频超分辨率服务

调用 Grok 官方 /rest/media/video/upscale 端点
将 480p 视频升级为 HD 版本
"""

import re
from typing import Optional

from curl_cffi.requests import AsyncSession

from app.core.logger import logger
from app.core.config import get_config
from app.core.exceptions import UpstreamException
from app.services.grok.utils.headers import build_grok_headers

VIDEO_UPSCALE_API = "https://grok.com/rest/media/video/upscale"


def extract_video_id(video_url: str) -> str:
    """从视频 URL 中提取 video ID"""
    if not video_url:
        return ""
    match = re.search(r"/generated/([0-9a-fA-F-]{32,36})/", video_url)
    if match:
        return match.group(1)
    match = re.search(r"/([0-9a-fA-F-]{32,36})/generated_video", video_url)
    if match:
        return match.group(1)
    return ""


class VideoUpscaleService:
    """视频超分辨率服务"""

    @staticmethod
    async def upscale(token: str, video_id: str) -> Optional[str]:
        """请求视频超分辨率，返回 HD URL 或 None

        Args:
            token: SSO token (不含 sso= 前缀)
            video_id: 视频 ID

        Returns:
            HD 视频 URL，或 None（失败时）
        """
        if not video_id:
            return None

        try:
            proxy = get_config("network.base_proxy_url")
            proxies = {"http": proxy, "https": proxy} if proxy else None
            headers = build_grok_headers(token)
            headers["Referer"] = f"https://grok.com/imagine/post/{video_id}"

            payload = {"videoId": video_id}
            logger.info(f"VideoUpscale request: video_id={video_id}")

            async with AsyncSession() as session:
                response = await session.post(
                    VIDEO_UPSCALE_API,
                    headers=headers,
                    json=payload,
                    timeout=get_config("network.timeout"),
                    proxies=proxies,
                    impersonate=get_config("security.browser"),
                )

            if response.status_code != 200:
                logger.warning(
                    f"VideoUpscale failed: status={response.status_code}, video_id={video_id}"
                )
                return None

            data = response.json() if response else {}
            hd_url = data.get("hdMediaUrl") if isinstance(data, dict) else None
            if hd_url:
                logger.info(f"VideoUpscale completed: {hd_url}")
                return hd_url

            logger.warning(f"VideoUpscale: no hdMediaUrl in response, video_id={video_id}")
            return None

        except Exception as e:
            logger.warning(f"VideoUpscale failed: {e}")
            return None

    @staticmethod
    async def upscale_video_url(
        video_url: str, token: str, enabled: bool = True
    ) -> str:
        """尝试超分辨率，失败时返回原始 URL

        Args:
            video_url: 原始视频 URL
            token: SSO token
            enabled: 是否启用超分辨率

        Returns:
            HD URL 或原始 URL
        """
        if not enabled or not video_url:
            return video_url

        video_id = extract_video_id(video_url)
        if not video_id:
            logger.warning("Video upscale skipped: unable to extract video id")
            return video_url

        hd_url = await VideoUpscaleService.upscale(token, video_id)
        return hd_url or video_url


__all__ = ["VideoUpscaleService", "extract_video_id"]
