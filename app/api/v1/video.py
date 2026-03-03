"""
Video Generation API 路由

提供独立的视频生成 REST API:
- POST /v1/video/start - 创建视频生成会话
- GET  /v1/video/sse   - SSE 流式获取视频
- POST /v1/video/stop  - 取消视频生成
"""

import asyncio
import re
import time
import uuid
from typing import Optional, List, Dict, Any

import orjson
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.logger import logger
from app.core.exceptions import AppException, ValidationException
from app.services.grok.services.media import VideoService
from app.services.grok.models.model import ModelService

router = APIRouter(tags=["Video"])

# 会话管理
VIDEO_SESSION_TTL = 600
_VIDEO_SESSIONS: dict[str, dict] = {}
_VIDEO_SESSIONS_LOCK = asyncio.Lock()

_VIDEO_RATIO_MAP = {
    "1280x720": "16:9",
    "720x1280": "9:16",
    "1792x1024": "3:2",
    "1024x1792": "2:3",
    "1024x1024": "1:1",
    "16:9": "16:9",
    "9:16": "9:16",
    "3:2": "3:2",
    "2:3": "2:3",
    "1:1": "1:1",
}


def _public_video_error_payload(exc: Exception) -> dict:
    """统一视频错误文案"""
    if isinstance(exc, AppException):
        return {"error": exc.message, "code": getattr(exc, "code", None) or "video_failed"}
    text = str(exc or "").lower()
    if "blocked by moderation" in text or "content moderated" in text:
        return {"error": "视频生成被拒绝，请调整提示词或素材后重试", "code": "video_rejected"}
    if "timed out" in text or "timeout" in text or "network" in text:
        return {"error": "视频生成失败：网络连接异常，请稍后重试", "code": "video_network_error"}
    return {"error": "视频生成失败，请稍后重试", "code": "video_failed"}


def _normalize_ratio(value: Optional[str]) -> str:
    raw = (value or "").strip()
    return _VIDEO_RATIO_MAP.get(raw, "")


def _validate_post_id(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if not re.fullmatch(r"[0-9a-fA-F-]{32,36}", v):
        raise ValidationException("Invalid post ID format", param="post_id", code="invalid_post_id")
    return v


async def _clean_sessions(now: float) -> None:
    expired = [
        key for key, info in _VIDEO_SESSIONS.items()
        if now - float(info.get("created_at") or 0) > VIDEO_SESSION_TTL
    ]
    for key in expired:
        _VIDEO_SESSIONS.pop(key, None)


async def _new_session(params: dict) -> str:
    task_id = uuid.uuid4().hex
    now = time.time()
    async with _VIDEO_SESSIONS_LOCK:
        await _clean_sessions(now)
        _VIDEO_SESSIONS[task_id] = {**params, "created_at": now}
    return task_id


async def _get_session(task_id: str) -> Optional[dict]:
    if not task_id:
        return None
    now = time.time()
    async with _VIDEO_SESSIONS_LOCK:
        await _clean_sessions(now)
        info = _VIDEO_SESSIONS.get(task_id)
        if not info:
            return None
        if now - float(info.get("created_at") or 0) > VIDEO_SESSION_TTL:
            _VIDEO_SESSIONS.pop(task_id, None)
            return None
        return dict(info)


async def _drop_sessions(task_ids: List[str]) -> int:
    if not task_ids:
        return 0
    removed = 0
    async with _VIDEO_SESSIONS_LOCK:
        for task_id in task_ids:
            if task_id and task_id in _VIDEO_SESSIONS:
                _VIDEO_SESSIONS.pop(task_id, None)
                removed += 1
    return removed


# ==================== 请求模型 ====================


class VideoStartRequest(BaseModel):
    prompt: Optional[str] = ""
    aspect_ratio: Optional[str] = "3:2"
    video_length: Optional[int] = 6
    resolution_name: Optional[str] = "480p"
    preset: Optional[str] = "normal"
    concurrent: Optional[int] = Field(1, ge=1, le=4)
    image_url: Optional[str] = None
    parent_post_id: Optional[str] = None
    source_image_url: Optional[str] = None
    # 视频延长
    is_video_extension: Optional[bool] = False
    extend_post_id: Optional[str] = None
    video_extension_start_time: Optional[float] = None
    original_post_id: Optional[str] = None
    file_attachment_id: Optional[str] = None
    stitch_with_extend: Optional[bool] = True


class VideoStopRequest(BaseModel):
    task_ids: List[str]


# ==================== 路由 ====================


@router.post("/video/start")
async def video_start(data: VideoStartRequest):
    """创建视频生成会话"""
    prompt = (data.prompt or "").strip()

    aspect_ratio = _normalize_ratio(data.aspect_ratio)
    if not aspect_ratio:
        raise ValidationException(
            "aspect_ratio must be one of ['16:9','9:16','3:2','2:3','1:1']",
            param="aspect_ratio",
            code="invalid_aspect_ratio",
        )

    video_length = int(data.video_length or 6)
    if video_length not in (6, 10, 15):
        raise ValidationException(
            "video_length must be 6, 10, or 15 seconds",
            param="video_length",
            code="invalid_video_length",
        )

    resolution_name = str(data.resolution_name or "480p")
    if resolution_name not in ("480p", "720p"):
        raise ValidationException(
            "resolution_name must be one of ['480p','720p']",
            param="resolution_name",
            code="invalid_resolution",
        )

    preset = str(data.preset or "normal")
    if preset not in ("fun", "normal", "spicy", "custom"):
        raise ValidationException(
            "preset must be one of ['fun','normal','spicy','custom']",
            param="preset",
            code="invalid_preset",
        )

    concurrent = min(4, max(1, int(data.concurrent or 1)))
    image_url = (data.image_url or "").strip() or None
    parent_post_id = _validate_post_id(data.parent_post_id or "")

    # 视频延长参数
    is_video_extension = bool(data.is_video_extension)
    extend_post_id = _validate_post_id(data.extend_post_id or "")
    video_extension_start_time = data.video_extension_start_time
    original_post_id = _validate_post_id(data.original_post_id or "")
    file_attachment_id = _validate_post_id(data.file_attachment_id or "")
    stitch_with_extend = bool(
        data.stitch_with_extend if data.stitch_with_extend is not None else True
    )

    if is_video_extension:
        if not extend_post_id:
            raise ValidationException(
                "extend_post_id is required for video extension",
                param="extend_post_id",
                code="missing_extend_post_id",
            )
        if video_extension_start_time is None or video_extension_start_time < 0:
            raise ValidationException(
                "video_extension_start_time must be a non-negative number",
                param="video_extension_start_time",
                code="invalid_start_time",
            )
        concurrent = 1  # 延长模式固定并发为 1
    else:
        if parent_post_id and image_url:
            raise ValidationException(
                "image_url and parent_post_id cannot be used together",
                param="image_url",
                code="conflict_params",
            )
        if not prompt and not image_url and not parent_post_id:
            raise ValidationException(
                "Prompt cannot be empty when no image_url/parent_post_id is provided",
                param="prompt",
                code="empty_prompt",
            )

    session_params = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "video_length": video_length,
        "resolution_name": resolution_name,
        "preset": preset,
        "image_url": image_url,
        "parent_post_id": parent_post_id,
        "source_image_url": (data.source_image_url or "").strip() or None,
        "is_video_extension": is_video_extension,
        "extend_post_id": extend_post_id,
        "video_extension_start_time": video_extension_start_time,
        "original_post_id": original_post_id,
        "file_attachment_id": file_attachment_id,
        "stitch_with_extend": stitch_with_extend,
    }

    task_ids: List[str] = []
    for _ in range(concurrent):
        task_id = await _new_session(session_params)
        task_ids.append(task_id)

    return {
        "task_id": task_ids[0],
        "task_ids": task_ids,
        "concurrent": concurrent,
        "aspect_ratio": aspect_ratio,
        "parent_post_id": parent_post_id,
        "extend_post_id": extend_post_id,
    }


@router.get("/video/sse")
async def video_sse(request: Request, task_id: str = Query("")):
    """SSE 流式获取视频生成结果"""
    session = await _get_session(task_id)
    if not session:
        return JSONResponse(
            status_code=404,
            content={"error": "Task not found", "code": "task_not_found"},
        )

    prompt = str(session.get("prompt") or "").strip()
    aspect_ratio = str(session.get("aspect_ratio") or "3:2")
    video_length = int(session.get("video_length") or 6)
    resolution_name = str(session.get("resolution_name") or "480p")
    preset = str(session.get("preset") or "normal")
    image_url = session.get("image_url")
    parent_post_id = str(session.get("parent_post_id") or "").strip()
    source_image_url = session.get("source_image_url")

    async def event_stream():
        try:
            model_id = "grok-imagine-1.0-video"
            model_info = ModelService.get(model_id)
            if not model_info or not model_info.is_video:
                payload = {"error": "Video model is not available.", "code": "model_not_supported"}
                yield f"data: {orjson.dumps(payload).decode()}\n\n"
                yield "data: [DONE]\n\n"
                return

            # 构建 messages
            if image_url:
                messages: List[Dict[str, Any]] = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ]
            else:
                messages = [{"role": "user", "content": prompt}]

            # 视频延长参数
            is_ext = bool(session.get("is_video_extension"))
            ext_post_id = str(session.get("extend_post_id") or "").strip() or None
            ext_start_time = session.get("video_extension_start_time")
            orig_post_id = str(session.get("original_post_id") or "").strip() or None
            file_att_id = str(session.get("file_attachment_id") or "").strip() or None
            stitch = bool(session.get("stitch_with_extend", True))

            stream = await VideoService.completions(
                model_id,
                messages,
                stream=True,
                aspect_ratio=aspect_ratio,
                video_length=video_length,
                resolution=resolution_name,
                preset=preset,
                parent_post_id=parent_post_id or None,
                extend_post_id=ext_post_id if is_ext else None,
                video_extension_start_time=ext_start_time if is_ext else None,
                original_post_id=orig_post_id if is_ext else None,
                file_attachment_id=file_att_id if is_ext else None,
                stitch_with_extend=stitch,
                source_image_url=source_image_url,
            )

            async for chunk in stream:
                if await request.is_disconnected():
                    logger.info(f"Video client disconnected: {task_id}")
                    break
                if task_id not in _VIDEO_SESSIONS:
                    logger.info(f"Video task stopped by user: {task_id}")
                    break
                yield chunk

        except Exception as e:
            logger.warning(f"Video SSE error: {e}")
            payload = _public_video_error_payload(e)
            yield f"data: {orjson.dumps(payload).decode()}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            async with _VIDEO_SESSIONS_LOCK:
                _VIDEO_SESSIONS.pop(task_id, None)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/video/stop")
async def video_stop(data: VideoStopRequest):
    """停止视频生成"""
    removed = await _drop_sessions(data.task_ids or [])
    return {"status": "success", "removed": removed}


__all__ = ["router"]
