from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Query,
    WebSocket,
    WebSocketDisconnect,
    File,
    Form,
    UploadFile,
)
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from typing import Optional, List
from pydantic import BaseModel, ValidationError
from app.core.auth import verify_api_key, verify_app_key, get_admin_api_key
from app.core.config import config, get_config
from app.core.batch_tasks import create_task, get_task, expire_task
from app.core.storage import get_storage, LocalStorage, RedisStorage, SQLStorage
from app.core.exceptions import AppException, ValidationException, ErrorType
from app.services.token.manager import get_token_manager
from app.services.grok.utils.batch import run_in_batches
import os
import time
import uuid
from pathlib import Path
import aiofiles
import asyncio
import orjson
import base64
import re
import random
from app.core.logger import logger
from app.api.v1.image import resolve_aspect_ratio, resolve_response_format, response_field_name, validate_edit_request, _get_token, ImageEditRequest
from app.services.grok.services.voice import VoiceService
from app.services.grok.services.image import image_service
from app.services.grok.services.chat import GrokChatService
from app.services.grok.services.assets import UploadService
from app.services.grok.services.media import VideoService
from app.services.grok.models.model import ModelService
from app.services.grok.processors.image_ws_processors import ImageWSCollectProcessor
from app.services.grok.processors import ImageStreamProcessor, ImageCollectProcessor
from app.services.token import EffortType

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "static"


router = APIRouter()

IMAGINE_SESSION_TTL = 600
_IMAGINE_SESSIONS: dict[str, dict] = {}
_IMAGINE_SESSIONS_LOCK = asyncio.Lock()


async def _cleanup_imagine_sessions(now: float) -> None:
    expired = [
        key
        for key, info in _IMAGINE_SESSIONS.items()
        if now - float(info.get("created_at") or 0) > IMAGINE_SESSION_TTL
    ]
    for key in expired:
        _IMAGINE_SESSIONS.pop(key, None)


async def _create_imagine_session(prompt: str, aspect_ratio: str) -> str:
    task_id = uuid.uuid4().hex
    now = time.time()
    async with _IMAGINE_SESSIONS_LOCK:
        await _cleanup_imagine_sessions(now)
        _IMAGINE_SESSIONS[task_id] = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "created_at": now,
        }
    return task_id


async def _get_imagine_session(task_id: str) -> Optional[dict]:
    if not task_id:
        return None
    now = time.time()
    async with _IMAGINE_SESSIONS_LOCK:
        await _cleanup_imagine_sessions(now)
        info = _IMAGINE_SESSIONS.get(task_id)
        if not info:
            return None
        created_at = float(info.get("created_at") or 0)
        if now - created_at > IMAGINE_SESSION_TTL:
            _IMAGINE_SESSIONS.pop(task_id, None)
            return None
        return dict(info)


async def _delete_imagine_session(task_id: str) -> None:
    if not task_id:
        return
    async with _IMAGINE_SESSIONS_LOCK:
        _IMAGINE_SESSIONS.pop(task_id, None)


async def _delete_imagine_sessions(task_ids: list[str]) -> int:
    if not task_ids:
        return 0
    removed = 0
    async with _IMAGINE_SESSIONS_LOCK:
        for task_id in task_ids:
            if task_id and task_id in _IMAGINE_SESSIONS:
                _IMAGINE_SESSIONS.pop(task_id, None)
                removed += 1
    return removed


def _collect_tokens(data: dict) -> list[str]:
    """从请求数据中收集 token 列表"""
    tokens = []
    if isinstance(data.get("token"), str) and data["token"].strip():
        tokens.append(data["token"].strip())
    if isinstance(data.get("tokens"), list):
        tokens.extend([str(t).strip() for t in data["tokens"] if str(t).strip()])
    return tokens


def _truncate_tokens(
    tokens: list[str], max_tokens: int, operation: str = "operation"
) -> tuple[list[str], bool, int]:
    """去重并截断 token 列表，返回 (unique_tokens, truncated, original_count)"""
    unique_tokens = list(dict.fromkeys(tokens))
    original_count = len(unique_tokens)
    truncated = False

    if len(unique_tokens) > max_tokens:
        unique_tokens = unique_tokens[:max_tokens]
        truncated = True
        logger.warning(
            f"{operation}: truncated from {original_count} to {max_tokens} tokens"
        )

    return unique_tokens, truncated, original_count


def _mask_token(token: str) -> str:
    """掩码 token 显示"""
    return f"{token[:8]}...{token[-8:]}" if len(token) > 20 else token


async def render_template(filename: str):
    """渲染指定模板"""
    template_path = TEMPLATE_DIR / filename
    if not template_path.exists():
        return HTMLResponse(f"Template {filename} not found.", status_code=404)

    async with aiofiles.open(template_path, "r", encoding="utf-8") as f:
        content = await f.read()
    return HTMLResponse(content)


@router.get("/admin/gallery")
async def gallery_page():
    """图片管理页面"""
    return await render_template("gallery/gallery.html")


@router.get("/admin/gallery/random")
async def gallery_random_page():
    """随机图片查看页面"""
    return await render_template("gallery/random.html")


@router.get("/admin/gallery/migrate")
async def gallery_migrate_page():
    """历史数据迁移页面"""
    return await render_template("gallery/migrate.html")


@router.get("/admin/prompts", response_class=HTMLResponse, include_in_schema=False)
async def prompts_page():
    """提示词管理页面"""
    return await render_template("prompts/prompts.html")


def _sse_event(payload: dict) -> str:
    return f"data: {orjson.dumps(payload).decode()}\n\n"


def _verify_stream_api_key(request: Request) -> None:
    api_key = get_admin_api_key()
    if not api_key:
        return
    key = request.query_params.get("api_key")
    if key != api_key:
        raise HTTPException(status_code=401, detail="Invalid authentication token")


@router.get("/api/v1/admin/batch/{task_id}/stream")
async def stream_batch(task_id: str, request: Request):
    _verify_stream_api_key(request)
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_stream():
        queue = task.attach()
        try:
            yield _sse_event({"type": "snapshot", **task.snapshot()})

            final = task.final_event()
            if final:
                yield _sse_event(final)
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    final = task.final_event()
                    if final:
                        yield _sse_event(final)
                        return
                    continue

                yield _sse_event(event)
                if event.get("type") in ("done", "error", "cancelled"):
                    return
        finally:
            task.detach(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post(
    "/api/v1/admin/batch/{task_id}/cancel", dependencies=[Depends(verify_api_key)]
)
async def cancel_batch(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.cancel()
    return {"status": "success"}


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_login_page():
    """管理后台登录页"""
    return await render_template("login/login.html")


@router.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/admin")


@router.get("/admin/config", response_class=HTMLResponse, include_in_schema=False)
async def admin_config_page():
    """配置管理页"""
    return await render_template("config/config.html")


@router.get("/admin/token", response_class=HTMLResponse, include_in_schema=False)
async def admin_token_page():
    """Token 管理页"""
    return await render_template("token/token.html")


@router.get("/admin/voice", response_class=HTMLResponse, include_in_schema=False)
async def admin_voice_page():
    """Voice Live 调试页"""
    return await render_template("voice/voice.html")


@router.get("/admin/imagine", response_class=HTMLResponse, include_in_schema=False)
async def admin_imagine_page():
    """Imagine 图片瀑布流"""
    return await render_template("imagine/imagine.html")


@router.get("/admin/img2img", response_class=HTMLResponse, include_in_schema=False)
async def admin_img2img_page():
    """图生图页面"""
    return await render_template("img2img/img2img.html")


class VoiceTokenResponse(BaseModel):
    token: str
    url: str
    participant_name: str = ""
    room_name: str = ""


@router.get(
    "/api/v1/admin/voice/token",
    dependencies=[Depends(verify_api_key)],
    response_model=VoiceTokenResponse,
)
async def admin_voice_token(
    voice: str = "ara",
    personality: str = "assistant",
    speed: float = 1.0,
):
    """获取 Grok Voice Mode (LiveKit) Token"""
    token_mgr = await get_token_manager()
    sso_token = None
    for pool_name in ("ssoBasic", "ssoSuper"):
        sso_token = token_mgr.get_token(pool_name)
        if sso_token:
            break

    if not sso_token:
        raise AppException(
            "No available tokens for voice mode",
            code="no_token",
            status_code=503,
        )

    service = VoiceService()
    try:
        data = await service.get_token(
            token=sso_token,
            voice=voice,
            personality=personality,
            speed=speed,
        )
        token = data.get("token")
        if not token:
            raise AppException(
                "Upstream returned no voice token",
                code="upstream_error",
                status_code=502,
            )

        return VoiceTokenResponse(
            token=token,
            url="wss://livekit.grok.com",
            participant_name="",
            room_name="",
        )

    except Exception as e:
        if isinstance(e, AppException):
            raise
        raise AppException(
            f"Voice token error: {str(e)}",
            code="voice_error",
            status_code=500,
        )


async def _verify_imagine_ws_auth(websocket: WebSocket) -> tuple[bool, Optional[str]]:
    task_id = websocket.query_params.get("task_id")
    if task_id:
        info = await _get_imagine_session(task_id)
        if info:
            return True, task_id

    api_key = get_admin_api_key()
    if not api_key:
        return True, None
    key = websocket.query_params.get("api_key")
    return key == api_key, None



@router.websocket("/api/v1/admin/imagine/ws")
async def admin_imagine_ws(websocket: WebSocket):
    ok, session_id = await _verify_imagine_ws_auth(websocket)
    if not ok:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    stop_event = asyncio.Event()
    run_task: Optional[asyncio.Task] = None

    async def _send(payload: dict) -> bool:
        try:
            await websocket.send_text(orjson.dumps(payload).decode())
            return True
        except Exception:
            return False

    async def _stop_run():
        nonlocal run_task
        stop_event.set()
        if run_task and not run_task.done():
            run_task.cancel()
            try:
                await run_task
            except Exception:
                pass
        run_task = None
        stop_event.clear()

    async def _run(prompt: str, aspect_ratio: str):
        model_id = "grok-imagine-1.0"
        model_info = ModelService.get(model_id)
        if not model_info or not model_info.is_image:
            await _send(
                {
                    "type": "error",
                    "message": "Image model is not available.",
                    "code": "model_not_supported",
                }
            )
            return

        token_mgr = await get_token_manager()
        enable_nsfw = bool(get_config("image.image_ws_nsfw", True))
        sequence = 0
        run_id = uuid.uuid4().hex

        await _send(
            {
                "type": "status",
                "status": "running",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "run_id": run_id,
            }
        )

        while not stop_event.is_set():
            try:
                await token_mgr.reload_if_stale()
                token = None
                for pool_name in ModelService.pool_candidates_for_model(
                    model_info.model_id
                ):
                    token = token_mgr.get_token(pool_name)
                    if token:
                        break

                if not token:
                    await _send(
                        {
                            "type": "error",
                            "message": "No available tokens. Please try again later.",
                            "code": "rate_limit_exceeded",
                        }
                    )
                    await asyncio.sleep(2)
                    continue

                upstream = image_service.stream(
                    token=token,
                    prompt=prompt,
                    aspect_ratio=aspect_ratio,
                    n=6,
                    enable_nsfw=enable_nsfw,
                )

                processor = ImageWSCollectProcessor(
                    model_info.model_id,
                    token,
                    n=6,
                    response_format="b64_json",
                )

                start_at = time.time()
                images = await processor.process(upstream)
                elapsed_ms = int((time.time() - start_at) * 1000)

                if images and all(img and img != "error" for img in images):
                    # 一次发送所有 6 张图片
                    for img_b64 in images:
                        sequence += 1
                        await _send(
                            {
                                "type": "image",
                                "b64_json": img_b64,
                                "sequence": sequence,
                                "created_at": int(time.time() * 1000),
                                "elapsed_ms": elapsed_ms,
                                "aspect_ratio": aspect_ratio,
                                "run_id": run_id,
                            }
                        )

                    # 图片已由客户端本地存储，服务端不再保存

                    # 消耗 token（6 张图片按高成本计算）
                    try:
                        effort = (
                            EffortType.HIGH
                            if (model_info and model_info.cost.value == "high")
                            else EffortType.LOW
                        )
                        await token_mgr.consume(token, effort)
                    except Exception as e:
                        logger.warning(f"Failed to consume token: {e}")
                else:
                    await _send(
                        {
                            "type": "error",
                            "message": "Image generation returned empty data.",
                            "code": "empty_image",
                        }
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Imagine stream error: {e}")
                await _send(
                    {
                        "type": "error",
                        "message": str(e),
                        "code": "internal_error",
                    }
                )
                await asyncio.sleep(1.5)

        await _send({"type": "status", "status": "stopped", "run_id": run_id})

    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except (RuntimeError, WebSocketDisconnect):
                # WebSocket already closed or disconnected
                break
            
            try:
                payload = orjson.loads(raw)
            except Exception:
                await _send(
                    {
                        "type": "error",
                        "message": "Invalid message format.",
                        "code": "invalid_payload",
                    }
                )
                continue

            msg_type = payload.get("type")
            if msg_type == "start":
                prompt = str(payload.get("prompt") or "").strip()
                if not prompt:
                    await _send(
                        {
                            "type": "error",
                            "message": "Prompt cannot be empty.",
                            "code": "empty_prompt",
                        }
                    )
                    continue
                ratio = str(payload.get("aspect_ratio") or "2:3").strip()
                if not ratio:
                    ratio = "2:3"
                ratio = resolve_aspect_ratio(ratio)
                await _stop_run()
                stop_event.clear()
                run_task = asyncio.create_task(_run(prompt, ratio))
            elif msg_type == "stop":
                await _stop_run()
            elif msg_type == "ping":
                await _send({"type": "pong"})
            else:
                await _send(
                    {
                        "type": "error",
                        "message": "Unknown command.",
                        "code": "unknown_command",
                    }
                )
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected by client")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        await _stop_run()

        try:
            from starlette.websockets import WebSocketState
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1000, reason="Server closing connection")
        except Exception as e:
            logger.debug(f"WebSocket close ignored: {e}")
        if session_id:
            await _delete_imagine_session(session_id)


class ImagineStartRequest(BaseModel):
    prompt: str
    aspect_ratio: Optional[str] = "2:3"


@router.post("/api/v1/admin/imagine/start", dependencies=[Depends(verify_api_key)])
async def admin_imagine_start(data: ImagineStartRequest):
    prompt = (data.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    ratio = resolve_aspect_ratio(str(data.aspect_ratio or "2:3").strip() or "2:3")
    task_id = await _create_imagine_session(prompt, ratio)
    return {"task_id": task_id, "aspect_ratio": ratio}


class ImagineStopRequest(BaseModel):
    task_ids: list[str]


@router.post("/api/v1/admin/imagine/stop", dependencies=[Depends(verify_api_key)])
async def admin_imagine_stop(data: ImagineStopRequest):
    removed = await _delete_imagine_sessions(data.task_ids or [])
    return {"status": "success", "removed": removed}


@router.get("/api/v1/admin/imagine/sse")
async def admin_imagine_sse(
    request: Request,
    task_id: str = Query(""),
    prompt: str = Query(""),
    aspect_ratio: str = Query("2:3"),
):
    """Imagine 图片瀑布流（SSE 兜底）"""
    session = None
    if task_id:
        session = await _get_imagine_session(task_id)
        if not session:
            raise HTTPException(status_code=404, detail="Task not found")
    else:
        _verify_stream_api_key(request)

    if session:
        prompt = str(session.get("prompt") or "").strip()
        ratio = str(session.get("aspect_ratio") or "2:3").strip() or "2:3"
    else:
        prompt = (prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")
        ratio = str(aspect_ratio or "2:3").strip() or "2:3"
        ratio = resolve_aspect_ratio(ratio)

    async def event_stream():
        try:
            model_id = "grok-imagine-1.0"
            model_info = ModelService.get(model_id)
            if not model_info or not model_info.is_image:
                yield _sse_event(
                    {
                        "type": "error",
                        "message": "Image model is not available.",
                        "code": "model_not_supported",
                    }
                )
                return

            token_mgr = await get_token_manager()
            enable_nsfw = bool(get_config("image.image_ws_nsfw", True))
            sequence = 0
            run_id = uuid.uuid4().hex

            yield _sse_event(
                {
                    "type": "status",
                    "status": "running",
                    "prompt": prompt,
                    "aspect_ratio": ratio,
                    "run_id": run_id,
                }
            )

            while True:
                if await request.is_disconnected():
                    break
                if task_id:
                    session_alive = await _get_imagine_session(task_id)
                    if not session_alive:
                        break

                try:
                    await token_mgr.reload_if_stale()
                    token = None
                    for pool_name in ModelService.pool_candidates_for_model(
                        model_info.model_id
                    ):
                        token = token_mgr.get_token(pool_name)
                        if token:
                            break

                    if not token:
                        yield _sse_event(
                            {
                                "type": "error",
                                "message": "No available tokens. Please try again later.",
                                "code": "rate_limit_exceeded",
                            }
                        )
                        await asyncio.sleep(2)
                        continue

                    upstream = image_service.stream(
                        token=token,
                        prompt=prompt,
                        aspect_ratio=ratio,
                        n=6,
                        enable_nsfw=enable_nsfw,
                    )

                    processor = ImageWSCollectProcessor(
                        model_info.model_id,
                        token,
                        n=6,
                        response_format="b64_json",
                    )

                    start_at = time.time()
                    images = await processor.process(upstream)
                    elapsed_ms = int((time.time() - start_at) * 1000)

                    if images and all(img and img != "error" for img in images):
                        for img_b64 in images:
                            sequence += 1
                            yield _sse_event(
                                {
                                    "type": "image",
                                    "b64_json": img_b64,
                                    "sequence": sequence,
                                    "created_at": int(time.time() * 1000),
                                    "elapsed_ms": elapsed_ms,
                                    "aspect_ratio": ratio,
                                    "run_id": run_id,
                                }
                            )

                        try:
                            effort = (
                                EffortType.HIGH
                                if (model_info and model_info.cost.value == "high")
                                else EffortType.LOW
                            )
                            await token_mgr.consume(token, effort)
                        except Exception as e:
                            logger.warning(f"Failed to consume token: {e}")
                    else:
                        yield _sse_event(
                            {
                                "type": "error",
                                "message": "Image generation returned empty data.",
                                "code": "empty_image",
                            }
                        )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Imagine SSE error: {e}")
                    yield _sse_event(
                        {"type": "error", "message": str(e), "code": "internal_error"}
                    )
                    await asyncio.sleep(1.5)

            yield _sse_event({"type": "status", "status": "stopped", "run_id": run_id})
        finally:
            if task_id:
                await _delete_imagine_session(task_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/api/v1/admin/login", dependencies=[Depends(verify_app_key)])
async def admin_login_api():
    """管理后台登录验证（使用 app_key）"""
    return {"status": "success", "api_key": get_admin_api_key()}


@router.get("/api/v1/admin/config", dependencies=[Depends(verify_api_key)])
async def get_config_api():
    """获取当前配置"""
    # 暴露原始配置字典
    return config._config


@router.post("/api/v1/admin/config", dependencies=[Depends(verify_api_key)])
async def update_config_api(data: dict):
    """更新配置"""
    try:
        await config.update(data)
        return {"status": "success", "message": "配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/admin/storage", dependencies=[Depends(verify_api_key)])
async def get_storage_info():
    """获取当前存储模式"""
    storage_type = os.getenv("SERVER_STORAGE_TYPE", "").lower()
    if not storage_type:
        storage_type = str(get_config("storage.type")).lower()
    if not storage_type:
        storage = get_storage()
        if isinstance(storage, LocalStorage):
            storage_type = "local"
        elif isinstance(storage, RedisStorage):
            storage_type = "redis"
        elif isinstance(storage, SQLStorage):
            storage_type = {
                "mysql": "mysql",
                "mariadb": "mysql",
                "postgres": "pgsql",
                "postgresql": "pgsql",
                "pgsql": "pgsql",
            }.get(storage.dialect, storage.dialect)
    return {"type": storage_type or "local"}


@router.get("/api/v1/admin/tokens", dependencies=[Depends(verify_api_key)])
async def get_tokens_api():
    """获取所有 Token"""
    storage = get_storage()
    tokens = await storage.load_tokens()
    return tokens or {}


@router.post("/api/v1/admin/tokens", dependencies=[Depends(verify_api_key)])
async def update_tokens_api(data: dict):
    """更新 Token 信息"""
    storage = get_storage()
    try:
        from app.services.token.manager import get_token_manager
        from app.services.token.models import TokenInfo

        async with storage.acquire_lock("tokens_save", timeout=10):
            existing = await storage.load_tokens() or {}
            normalized = {}
            allowed_fields = set(TokenInfo.model_fields.keys())
            existing_map = {}
            for pool_name, tokens in existing.items():
                if not isinstance(tokens, list):
                    continue
                pool_map = {}
                for item in tokens:
                    if isinstance(item, str):
                        token_data = {"token": item}
                    elif isinstance(item, dict):
                        token_data = dict(item)
                    else:
                        continue
                    raw_token = token_data.get("token")
                    if isinstance(raw_token, str) and raw_token.startswith("sso="):
                        token_data["token"] = raw_token[4:]
                    token_key = token_data.get("token")
                    if isinstance(token_key, str):
                        pool_map[token_key] = token_data
                existing_map[pool_name] = pool_map
            for pool_name, tokens in (data or {}).items():
                if not isinstance(tokens, list):
                    continue
                pool_list = []
                for item in tokens:
                    if isinstance(item, str):
                        token_data = {"token": item}
                    elif isinstance(item, dict):
                        token_data = dict(item)
                    else:
                        continue

                    raw_token = token_data.get("token")
                    if isinstance(raw_token, str) and raw_token.startswith("sso="):
                        token_data["token"] = raw_token[4:]

                    base = existing_map.get(pool_name, {}).get(
                        token_data.get("token"), {}
                    )
                    merged = dict(base)
                    merged.update(token_data)
                    if merged.get("tags") is None:
                        merged["tags"] = []

                    filtered = {k: v for k, v in merged.items() if k in allowed_fields}
                    try:
                        info = TokenInfo(**filtered)
                        pool_list.append(info.model_dump())
                    except Exception as e:
                        logger.warning(f"Skip invalid token in pool '{pool_name}': {e}")
                        continue
                normalized[pool_name] = pool_list

            await storage.save_tokens(normalized)
            mgr = await get_token_manager()
            await mgr.reload()
        return {"status": "success", "message": "Token 已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/admin/tokens/refresh", dependencies=[Depends(verify_api_key)])
async def refresh_tokens_api(data: dict):
    """刷新 Token 状态"""
    try:
        mgr = await get_token_manager()
        tokens = _collect_tokens(data)

        if not tokens:
            raise HTTPException(status_code=400, detail="No tokens provided")

        # 去重并截断
        max_tokens = int(get_config("performance.usage_max_tokens"))
        unique_tokens, truncated, original_count = _truncate_tokens(
            tokens, max_tokens, "Usage refresh"
        )

        # 批量执行配置
        max_concurrent = get_config("performance.usage_max_concurrent")
        batch_size = get_config("performance.usage_batch_size")

        async def _refresh_one(t):
            return await mgr.sync_usage(
                t, "grok-3", consume_on_fail=False, is_usage=False
            )

        raw_results = await run_in_batches(
            unique_tokens,
            _refresh_one,
            max_concurrent=max_concurrent,
            batch_size=batch_size,
        )

        results = {}
        for token, res in raw_results.items():
            if res.get("ok"):
                results[token] = res.get("data", False)
            else:
                results[token] = False

        response = {"status": "success", "results": results}
        if truncated:
            response["warning"] = (
                f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
            )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/api/v1/admin/tokens/refresh/async", dependencies=[Depends(verify_api_key)]
)
async def refresh_tokens_api_async(data: dict):
    """刷新 Token 状态（异步批量 + SSE 进度）"""
    mgr = await get_token_manager()
    tokens = _collect_tokens(data)

    if not tokens:
        raise HTTPException(status_code=400, detail="No tokens provided")

    # 去重并截断
    max_tokens = int(get_config("performance.usage_max_tokens"))
    unique_tokens, truncated, original_count = _truncate_tokens(
        tokens, max_tokens, "Usage refresh"
    )

    max_concurrent = get_config("performance.usage_max_concurrent")
    batch_size = get_config("performance.usage_batch_size")

    task = create_task(len(unique_tokens))

    async def _run():
        try:

            async def _refresh_one(t: str):
                return await mgr.sync_usage(
                    t, "grok-3", consume_on_fail=False, is_usage=False
                )

            async def _on_item(item: str, res: dict):
                task.record(bool(res.get("ok")))

            raw_results = await run_in_batches(
                unique_tokens,
                _refresh_one,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
                on_item=_on_item,
                should_cancel=lambda: task.cancelled,
            )

            if task.cancelled:
                task.finish_cancelled()
                return

            results: dict[str, bool] = {}
            ok_count = 0
            fail_count = 0
            for token, res in raw_results.items():
                if res.get("ok") and res.get("data") is True:
                    ok_count += 1
                    results[token] = True
                else:
                    fail_count += 1
                    results[token] = False

            await mgr._save()

            result = {
                "status": "success",
                "summary": {
                    "total": len(unique_tokens),
                    "ok": ok_count,
                    "fail": fail_count,
                },
                "results": results,
            }
            warning = None
            if truncated:
                warning = (
                    f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
                )
            task.finish(result, warning=warning)
        except Exception as e:
            task.fail_task(str(e))
        finally:
            asyncio.create_task(expire_task(task.id, 300))

    asyncio.create_task(_run())

    return {
        "status": "success",
        "task_id": task.id,
        "total": len(unique_tokens),
    }


@router.post("/api/v1/admin/tokens/nsfw/enable", dependencies=[Depends(verify_api_key)])
async def enable_nsfw_api(data: dict):
    """批量开启 NSFW (Unhinged) 模式"""
    from app.services.grok.services.nsfw import NSFWService

    try:
        mgr = await get_token_manager()
        nsfw_service = NSFWService()

        # 收集 token 列表
        tokens = _collect_tokens(data)

        # 若未指定，则使用所有 pool 中的 token
        if not tokens:
            for pool_name, pool in mgr.pools.items():
                for info in pool.list():
                    raw = (
                        info.token[4:] if info.token.startswith("sso=") else info.token
                    )
                    tokens.append(raw)

        if not tokens:
            raise HTTPException(status_code=400, detail="No tokens available")

        # 去重并截断
        max_tokens = int(get_config("performance.nsfw_max_tokens"))
        unique_tokens, truncated, original_count = _truncate_tokens(
            tokens, max_tokens, "NSFW enable"
        )

        # 批量执行配置
        max_concurrent = get_config("performance.nsfw_max_concurrent")
        batch_size = get_config("performance.nsfw_batch_size")

        # 定义 worker
        async def _enable(token: str):
            result = await nsfw_service.enable(token)
            # 成功后添加 nsfw tag
            if result.success:
                await mgr.add_tag(token, "nsfw")
            return {
                "success": result.success,
                "http_status": result.http_status,
                "grpc_status": result.grpc_status,
                "grpc_message": result.grpc_message,
                "error": result.error,
            }

        # 执行批量操作
        raw_results = await run_in_batches(
            unique_tokens, _enable, max_concurrent=max_concurrent, batch_size=batch_size
        )

        # 构造返回结果（mask token）
        results = {}
        ok_count = 0
        fail_count = 0

        for token, res in raw_results.items():
            masked = _mask_token(token)
            if res.get("ok") and res.get("data", {}).get("success"):
                ok_count += 1
                results[masked] = res.get("data", {})
            else:
                fail_count += 1
                results[masked] = res.get("data") or {"error": res.get("error")}

        # 立即保存 token 变更
        await mgr._save()

        response = {
            "status": "success",
            "summary": {
                "total": len(unique_tokens),
                "ok": ok_count,
                "fail": fail_count,
            },
            "results": results,
        }

        # 添加截断提示
        if truncated:
            response["warning"] = (
                f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
            )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enable NSFW failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/api/v1/admin/tokens/nsfw/enable/async", dependencies=[Depends(verify_api_key)]
)
async def enable_nsfw_api_async(data: dict):
    """批量开启 NSFW (Unhinged) 模式（异步批量 + SSE 进度）"""
    from app.services.grok.services.nsfw import NSFWService

    mgr = await get_token_manager()
    nsfw_service = NSFWService()

    tokens = _collect_tokens(data)

    if not tokens:
        for pool_name, pool in mgr.pools.items():
            for info in pool.list():
                raw = info.token[4:] if info.token.startswith("sso=") else info.token
                tokens.append(raw)

    if not tokens:
        raise HTTPException(status_code=400, detail="No tokens available")

    # 去重并截断
    max_tokens = int(get_config("performance.nsfw_max_tokens"))
    unique_tokens, truncated, original_count = _truncate_tokens(
        tokens, max_tokens, "NSFW enable"
    )

    max_concurrent = get_config("performance.nsfw_max_concurrent")
    batch_size = get_config("performance.nsfw_batch_size")

    task = create_task(len(unique_tokens))

    async def _run():
        try:

            async def _enable(token: str):
                result = await nsfw_service.enable(token)
                if result.success:
                    await mgr.add_tag(token, "nsfw")
                return {
                    "success": result.success,
                    "http_status": result.http_status,
                    "grpc_status": result.grpc_status,
                    "grpc_message": result.grpc_message,
                    "error": result.error,
                }

            async def _on_item(item: str, res: dict):
                ok = bool(res.get("ok") and res.get("data", {}).get("success"))
                task.record(ok)

            raw_results = await run_in_batches(
                unique_tokens,
                _enable,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
                on_item=_on_item,
                should_cancel=lambda: task.cancelled,
            )

            if task.cancelled:
                task.finish_cancelled()
                return

            results = {}
            ok_count = 0
            fail_count = 0
            for token, res in raw_results.items():
                masked = f"{token[:8]}...{token[-8:]}" if len(token) > 20 else token
                if res.get("ok") and res.get("data", {}).get("success"):
                    ok_count += 1
                    results[masked] = res.get("data", {})
                else:
                    fail_count += 1
                    results[masked] = res.get("data") or {"error": res.get("error")}

            await mgr._save()

            result = {
                "status": "success",
                "summary": {
                    "total": len(unique_tokens),
                    "ok": ok_count,
                    "fail": fail_count,
                },
                "results": results,
            }
            warning = None
            if truncated:
                warning = (
                    f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
                )
            task.finish(result, warning=warning)
        except Exception as e:
            task.fail_task(str(e))
        finally:
            asyncio.create_task(expire_task(task.id, 300))

    asyncio.create_task(_run())

    return {
        "status": "success",
        "task_id": task.id,
        "total": len(unique_tokens),
    }


@router.get("/admin/cache", response_class=HTMLResponse, include_in_schema=False)
async def admin_cache_page():
    """缓存管理页"""
    return await render_template("cache/cache.html")


@router.get("/api/v1/admin/cache", dependencies=[Depends(verify_api_key)])
async def get_cache_stats_api(request: Request):
    """获取缓存统计"""
    from app.services.grok.services.assets import DownloadService, ListService
    from app.services.token.manager import get_token_manager
    from app.services.grok.utils.batch import run_in_batches

    try:
        dl_service = DownloadService()
        image_stats = dl_service.get_stats("image")
        video_stats = dl_service.get_stats("video")

        mgr = await get_token_manager()
        pools = mgr.pools
        accounts = []
        for pool_name, pool in pools.items():
            for info in pool.list():
                raw_token = (
                    info.token[4:] if info.token.startswith("sso=") else info.token
                )
                masked = (
                    f"{raw_token[:8]}...{raw_token[-16:]}"
                    if len(raw_token) > 24
                    else raw_token
                )
                accounts.append(
                    {
                        "token": raw_token,
                        "token_masked": masked,
                        "pool": pool_name,
                        "status": info.status,
                        "last_asset_clear_at": info.last_asset_clear_at,
                    }
                )

        scope = request.query_params.get("scope")
        selected_token = request.query_params.get("token")
        tokens_param = request.query_params.get("tokens")
        selected_tokens = []
        if tokens_param:
            selected_tokens = [t.strip() for t in tokens_param.split(",") if t.strip()]

        online_stats = {
            "count": 0,
            "status": "unknown",
            "token": None,
            "last_asset_clear_at": None,
        }
        online_details = []
        account_map = {a["token"]: a for a in accounts}
        max_concurrent = max(1, int(get_config("performance.assets_max_concurrent")))
        batch_size = max(1, int(get_config("performance.assets_batch_size")))
        max_tokens = int(get_config("performance.assets_max_tokens"))

        truncated = False
        original_count = 0

        async def _fetch_assets(token: str):
            list_service = ListService()
            try:
                return await list_service.count(token)
            finally:
                await list_service.close()

        async def _fetch_detail(token: str):
            account = account_map.get(token)
            try:
                count = await _fetch_assets(token)
                return {
                    "detail": {
                        "token": token,
                        "token_masked": account["token_masked"] if account else token,
                        "count": count,
                        "status": "ok",
                        "last_asset_clear_at": account["last_asset_clear_at"]
                        if account
                        else None,
                    },
                    "count": count,
                }
            except Exception as e:
                return {
                    "detail": {
                        "token": token,
                        "token_masked": account["token_masked"] if account else token,
                        "count": 0,
                        "status": f"error: {str(e)}",
                        "last_asset_clear_at": account["last_asset_clear_at"]
                        if account
                        else None,
                    },
                    "count": 0,
                }

        if selected_tokens:
            selected_tokens, truncated, original_count = _truncate_tokens(
                selected_tokens, max_tokens, "Assets fetch"
            )
            total = 0
            raw_results = await run_in_batches(
                selected_tokens,
                _fetch_detail,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
            )
            for token, res in raw_results.items():
                if res.get("ok"):
                    data = res.get("data", {})
                    detail = data.get("detail")
                    total += data.get("count", 0)
                else:
                    account = account_map.get(token)
                    detail = {
                        "token": token,
                        "token_masked": account["token_masked"] if account else token,
                        "count": 0,
                        "status": f"error: {res.get('error')}",
                        "last_asset_clear_at": account["last_asset_clear_at"]
                        if account
                        else None,
                    }
                if detail:
                    online_details.append(detail)
            online_stats = {
                "count": total,
                "status": "ok" if selected_tokens else "no_token",
                "token": None,
                "last_asset_clear_at": None,
            }
            scope = "selected"
        elif scope == "all":
            total = 0
            tokens = list(dict.fromkeys([account["token"] for account in accounts]))
            original_count = len(tokens)
            if len(tokens) > max_tokens:
                tokens = tokens[:max_tokens]
                truncated = True
            raw_results = await run_in_batches(
                tokens,
                _fetch_detail,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
            )
            for token, res in raw_results.items():
                if res.get("ok"):
                    data = res.get("data", {})
                    detail = data.get("detail")
                    total += data.get("count", 0)
                else:
                    account = account_map.get(token)
                    detail = {
                        "token": token,
                        "token_masked": account["token_masked"] if account else token,
                        "count": 0,
                        "status": f"error: {res.get('error')}",
                        "last_asset_clear_at": account["last_asset_clear_at"]
                        if account
                        else None,
                    }
                if detail:
                    online_details.append(detail)
            online_stats = {
                "count": total,
                "status": "ok" if accounts else "no_token",
                "token": None,
                "last_asset_clear_at": None,
            }
        else:
            token = selected_token
            if token:
                try:
                    count = await _fetch_assets(token)
                    match = next((a for a in accounts if a["token"] == token), None)
                    online_stats = {
                        "count": count,
                        "status": "ok",
                        "token": token,
                        "token_masked": match["token_masked"] if match else token,
                        "last_asset_clear_at": match["last_asset_clear_at"]
                        if match
                        else None,
                    }
                except Exception as e:
                    match = next((a for a in accounts if a["token"] == token), None)
                    online_stats = {
                        "count": 0,
                        "status": f"error: {str(e)}",
                        "token": token,
                        "token_masked": match["token_masked"] if match else token,
                        "last_asset_clear_at": match["last_asset_clear_at"]
                        if match
                        else None,
                    }
            else:
                online_stats = {
                    "count": 0,
                    "status": "not_loaded",
                    "token": None,
                    "last_asset_clear_at": None,
                }

        response = {
            "local_image": image_stats,
            "local_video": video_stats,
            "online": online_stats,
            "online_accounts": accounts,
            "online_scope": scope or "none",
            "online_details": online_details,
        }
        if truncated:
            response["warning"] = (
                f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
            )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/api/v1/admin/cache/online/load/async", dependencies=[Depends(verify_api_key)]
)
async def load_online_cache_api_async(data: dict):
    """在线资产统计（异步批量 + SSE 进度）"""
    from app.services.grok.services.assets import DownloadService, ListService
    from app.services.token.manager import get_token_manager
    from app.services.grok.utils.batch import run_in_batches

    mgr = await get_token_manager()

    # 账号列表
    accounts = []
    for pool_name, pool in mgr.pools.items():
        for info in pool.list():
            raw_token = info.token[4:] if info.token.startswith("sso=") else info.token
            masked = (
                f"{raw_token[:8]}...{raw_token[-16:]}"
                if len(raw_token) > 24
                else raw_token
            )
            accounts.append(
                {
                    "token": raw_token,
                    "token_masked": masked,
                    "pool": pool_name,
                    "status": info.status,
                    "last_asset_clear_at": info.last_asset_clear_at,
                }
            )

    account_map = {a["token"]: a for a in accounts}

    tokens = data.get("tokens")
    scope = data.get("scope")
    selected_tokens: list[str] = []
    if isinstance(tokens, list):
        selected_tokens = [str(t).strip() for t in tokens if str(t).strip()]

    if not selected_tokens and scope == "all":
        selected_tokens = [account["token"] for account in accounts]
        scope = "all"
    elif selected_tokens:
        scope = "selected"
    else:
        raise HTTPException(status_code=400, detail="No tokens provided")

    max_tokens = int(get_config("performance.assets_max_tokens"))
    selected_tokens, truncated, original_count = _truncate_tokens(
        selected_tokens, max_tokens, "Assets load"
    )

    max_concurrent = get_config("performance.assets_max_concurrent")
    batch_size = get_config("performance.assets_batch_size")

    task = create_task(len(selected_tokens))

    async def _run():
        try:
            dl_service = DownloadService()
            image_stats = dl_service.get_stats("image")
            video_stats = dl_service.get_stats("video")

            async def _fetch_detail(token: str):
                account = account_map.get(token)
                list_service = ListService()
                try:
                    count = await list_service.count(token)
                    detail = {
                        "token": token,
                        "token_masked": account["token_masked"] if account else token,
                        "count": count,
                        "status": "ok",
                        "last_asset_clear_at": account["last_asset_clear_at"]
                        if account
                        else None,
                    }
                    return {"ok": True, "detail": detail, "count": count}
                except Exception as e:
                    detail = {
                        "token": token,
                        "token_masked": account["token_masked"] if account else token,
                        "count": 0,
                        "status": f"error: {str(e)}",
                        "last_asset_clear_at": account["last_asset_clear_at"]
                        if account
                        else None,
                    }
                    return {"ok": False, "detail": detail, "count": 0}
                finally:
                    await list_service.close()

            async def _on_item(item: str, res: dict):
                ok = bool(res.get("data", {}).get("ok"))
                task.record(ok)

            raw_results = await run_in_batches(
                selected_tokens,
                _fetch_detail,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
                on_item=_on_item,
                should_cancel=lambda: task.cancelled,
            )

            if task.cancelled:
                task.finish_cancelled()
                return

            online_details = []
            total = 0
            for token, res in raw_results.items():
                data = res.get("data", {})
                detail = data.get("detail")
                if detail:
                    online_details.append(detail)
                total += data.get("count", 0)

            online_stats = {
                "count": total,
                "status": "ok" if selected_tokens else "no_token",
                "token": None,
                "last_asset_clear_at": None,
            }

            result = {
                "local_image": image_stats,
                "local_video": video_stats,
                "online": online_stats,
                "online_accounts": accounts,
                "online_scope": scope or "none",
                "online_details": online_details,
            }
            warning = None
            if truncated:
                warning = (
                    f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
                )
            task.finish(result, warning=warning)
        except Exception as e:
            task.fail_task(str(e))
        finally:
            asyncio.create_task(expire_task(task.id, 300))

    asyncio.create_task(_run())

    return {
        "status": "success",
        "task_id": task.id,
        "total": len(selected_tokens),
    }


@router.post("/api/v1/admin/cache/clear", dependencies=[Depends(verify_api_key)])
async def clear_local_cache_api(data: dict):
    """清理本地缓存"""
    from app.services.grok.services.assets import DownloadService

    cache_type = data.get("type", "image")

    try:
        dl_service = DownloadService()
        result = dl_service.clear(cache_type)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/admin/cache/list", dependencies=[Depends(verify_api_key)])
async def list_local_cache_api(
    cache_type: str = "image",
    type_: str = Query(default=None, alias="type"),
    page: int = 1,
    page_size: int = 1000,
):
    """列出本地缓存文件"""
    from app.services.grok.services.assets import DownloadService

    try:
        if type_:
            cache_type = type_
        dl_service = DownloadService()
        result = dl_service.list_files(cache_type, page, page_size)
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/admin/cache/item/delete", dependencies=[Depends(verify_api_key)])
async def delete_local_cache_item_api(data: dict):
    """删除单个本地缓存文件"""
    from app.services.grok.services.assets import DownloadService

    cache_type = data.get("type", "image")
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Missing file name")
    try:
        dl_service = DownloadService()
        result = dl_service.delete_file(cache_type, name)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/admin/cache/online/clear", dependencies=[Depends(verify_api_key)])
async def clear_online_cache_api(data: dict):
    """清理在线缓存"""
    from app.services.grok.services.assets import DeleteService
    from app.services.token.manager import get_token_manager
    from app.services.grok.utils.batch import run_in_batches

    delete_service = None
    try:
        mgr = await get_token_manager()
        tokens = data.get("tokens")
        delete_service = DeleteService()

        if isinstance(tokens, list):
            token_list = [t.strip() for t in tokens if isinstance(t, str) and t.strip()]
            if not token_list:
                raise HTTPException(status_code=400, detail="No tokens provided")

            # 去重并保持顺序
            token_list = list(dict.fromkeys(token_list))

            # 最大数量限制
            max_tokens = int(get_config("performance.assets_max_tokens"))
            token_list, truncated, original_count = _truncate_tokens(
                token_list, max_tokens, "Clear online cache"
            )

            results = {}
            max_concurrent = max(
                1, int(get_config("performance.assets_max_concurrent"))
            )
            batch_size = max(1, int(get_config("performance.assets_batch_size")))

            async def _clear_one(t: str):
                try:
                    result = await delete_service.delete_all(t)
                    await mgr.mark_asset_clear(t)
                    return {"status": "success", "result": result}
                except Exception as e:
                    return {"status": "error", "error": str(e)}

            raw_results = await run_in_batches(
                token_list,
                _clear_one,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
            )
            for token, res in raw_results.items():
                if res.get("ok"):
                    results[token] = res.get("data", {})
                else:
                    results[token] = {"status": "error", "error": res.get("error")}

            # 立即保存 token 变更
            await mgr._save()

            response = {"status": "success", "results": results}
            if truncated:
                response["warning"] = (
                    f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
                )
            return response

        token = data.get("token") or mgr.get_token()
        if not token:
            raise HTTPException(
                status_code=400, detail="No available token to perform cleanup"
            )

        result = await delete_service.delete_all(token)
        await mgr.mark_asset_clear(token)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if delete_service:
            await delete_service.close()


@router.post(
    "/api/v1/admin/cache/online/clear/async", dependencies=[Depends(verify_api_key)]
)
async def clear_online_cache_api_async(data: dict):
    """清理在线缓存（异步批量 + SSE 进度）"""
    from app.services.grok.services.assets import DeleteService
    from app.services.token.manager import get_token_manager
    from app.services.grok.utils.batch import run_in_batches

    mgr = await get_token_manager()
    tokens = data.get("tokens")
    if not isinstance(tokens, list):
        raise HTTPException(status_code=400, detail="No tokens provided")

    token_list = [t.strip() for t in tokens if isinstance(t, str) and t.strip()]
    if not token_list:
        raise HTTPException(status_code=400, detail="No tokens provided")

    max_tokens = int(get_config("performance.assets_max_tokens"))
    token_list, truncated, original_count = _truncate_tokens(
        token_list, max_tokens, "Clear online cache async"
    )

    max_concurrent = get_config("performance.assets_max_concurrent")
    batch_size = get_config("performance.assets_batch_size")

    task = create_task(len(token_list))

    async def _run():
        delete_service = DeleteService()
        try:

            async def _clear_one(t: str):
                try:
                    result = await delete_service.delete_all(t)
                    await mgr.mark_asset_clear(t)
                    return {"ok": True, "result": result}
                except Exception as e:
                    return {"ok": False, "error": str(e)}

            async def _on_item(item: str, res: dict):
                ok = bool(res.get("data", {}).get("ok"))
                task.record(ok)

            raw_results = await run_in_batches(
                token_list,
                _clear_one,
                max_concurrent=max_concurrent,
                batch_size=batch_size,
                on_item=_on_item,
                should_cancel=lambda: task.cancelled,
            )

            if task.cancelled:
                task.finish_cancelled()
                return

            results = {}
            ok_count = 0
            fail_count = 0
            for token, res in raw_results.items():
                data = res.get("data", {})
                if data.get("ok"):
                    ok_count += 1
                    results[token] = {"status": "success", "result": data.get("result")}
                else:
                    fail_count += 1
                    results[token] = {"status": "error", "error": data.get("error")}

            # 立即保存 token 变更
            await mgr._save()

            result = {
                "status": "success",
                "summary": {
                    "total": len(token_list),
                    "ok": ok_count,
                    "fail": fail_count,
                },
                "results": results,
            }
            warning = None
            if truncated:
                warning = (
                    f"数量超出限制，仅处理前 {max_tokens} 个（共 {original_count} 个）"
                )
            task.finish(result, warning=warning)
        except Exception as e:
            task.fail_task(str(e))
        finally:
            await delete_service.close()
            asyncio.create_task(expire_task(task.id, 300))

    asyncio.create_task(_run())

    return {
        "status": "success",
        "task_id": task.id,
        "total": len(token_list),
    }


@router.post("/api/v1/admin/img2img")
async def admin_img2img(
    prompt: str = Form(...),
    image: List[UploadFile] = File(...),
    model: Optional[str] = Form("grok-imagine-1.0-edit"),
    n: int = Form(1),
    size: str = Form("1024x1024"),
    quality: str = Form("standard"),
    response_format: Optional[str] = Form(None),
    style: Optional[str] = Form(None),
    stream: Optional[bool] = Form(False),
    # 图片编辑控制参数
    strength: Optional[float] = Form(0.85),
    edit_mode: Optional[str] = Form("comprehensive"),
    preserve_background: Optional[bool] = Form(False),
    guidance_scale: Optional[float] = Form(7.5),
):
    """
    Admin 图生图 API

    不需要用户 API Key，使用内部 token 池
    """
    if response_format is None:
        response_format = resolve_response_format(None)

    try:
        edit_request = ImageEditRequest(
            prompt=prompt,
            model=model,
            n=n,
            size=size,
            quality=quality,
            response_format=response_format,
            style=style,
            stream=stream,
            strength=strength,
            edit_mode=edit_mode,
            preserve_background=preserve_background,
            guidance_scale=guidance_scale,
        )
    except ValidationError as exc:
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = first.get("loc", [])
            msg = first.get("msg", "Invalid request")
            code = first.get("type", "invalid_value")
            param_parts = [
                str(x) for x in loc if not (isinstance(x, int) or str(x).isdigit())
            ]
            param = ".".join(param_parts) if param_parts else None
            raise ValidationException(message=msg, param=param, code=code)
        raise ValidationException(message="Invalid request", code="invalid_value")

    if edit_request.stream is None:
        edit_request.stream = False

    response_format = resolve_response_format(edit_request.response_format)
    edit_request.response_format = response_format
    response_field = response_field_name(response_format)

    # 参数验证
    validate_edit_request(edit_request, image)

    max_image_bytes = 50 * 1024 * 1024
    allowed_types = {"image/png", "image/jpeg", "image/webp", "image/jpg"}

    images: List[str] = []
    for item in image:
        content = await item.read()
        await item.close()
        if not content:
            raise ValidationException(
                message="File content is empty",
                param="image",
                code="empty_file",
            )
        if len(content) > max_image_bytes:
            raise ValidationException(
                message="Image file too large. Maximum is 50MB.",
                param="image",
                code="file_too_large",
            )
        mime = (item.content_type or "").lower()
        if mime == "image/jpg":
            mime = "image/jpeg"
        ext = Path(item.filename or "").suffix.lower()
        if mime not in allowed_types:
            if ext in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif ext == ".png":
                mime = "image/png"
            elif ext == ".webp":
                mime = "image/webp"
            else:
                raise ValidationException(
                    message="Unsupported image type. Supported: png, jpg, webp.",
                    param="image",
                    code="invalid_image_type",
                )
        b64 = base64.b64encode(content).decode()
        images.append(f"data:{mime};base64,{b64}")

    # 获取 token 和模型信息
    token_mgr, token = await _get_token(edit_request.model)
    model_info = ModelService.get(edit_request.model)

    # 上传图片（不复用 session 避免 HTTP/2 连接问题）- 支持token轮换重试
    image_urls: List[str] = []
    upload_service = UploadService()
    max_token_retries = 3  # 最多尝试3个不同的token
    current_token = token

    try:
        for image_idx, image_data in enumerate(images):
            uploaded = False
            last_error = None

            # 对每张图片尝试上传，如果遇到403则轮换token重试
            for retry_idx in range(max_token_retries):
                try:
                    file_id, file_uri = await upload_service.upload(image_data, current_token, reuse_session=False)
                    if file_uri:
                        if file_uri.startswith("http"):
                            image_urls.append(file_uri)
                        else:
                            image_urls.append(f"https://assets.grok.com/{file_uri.lstrip('/')}")
                        uploaded = True
                        logger.info(f"图片 {image_idx + 1} 上传成功 (token尝试次数: {retry_idx + 1})")
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
                            f"图片 {image_idx + 1} 上传遇到403错误 (尝试 {retry_idx + 1}/{max_token_retries})，"
                            f"尝试轮换token重试..."
                        )
                        # 获取新的token
                        try:
                            token_mgr, new_token = await _get_token(edit_request.model)
                            if new_token != current_token:
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

            if not uploaded:
                logger.error(f"图片 {image_idx + 1} 上传失败，已尝试 {max_token_retries} 个token")
                if last_error:
                    raise last_error
    finally:
        await upload_service.close()

    if not image_urls:
        raise AppException(
            message="Image upload failed",
            error_type=ErrorType.SERVER.value,
            code="upload_failed",
        )

    parent_post_id = None
    try:
        media_service = VideoService()
        parent_post_id = await media_service.create_image_post(token, image_urls[0])
        logger.debug(f"Parent post ID: {parent_post_id}")
    except Exception as e:
        logger.warning(f"Create image post failed: {e}")

    if not parent_post_id:
        for url in image_urls:
            match = re.search(r"/generated/([a-f0-9-]+)/", url)
            if match:
                parent_post_id = match.group(1)
                logger.debug(f"Parent post ID: {parent_post_id}")
                break
            match = re.search(r"/users/[^/]+/([a-f0-9-]+)/content", url)
            if match:
                parent_post_id = match.group(1)
                logger.debug(f"Parent post ID: {parent_post_id}")
                break

    # 构建imageEditModelConfig，添加编辑控制参数
    image_edit_config = {
        "imageReferences": image_urls,
    }

    # 添加编辑强度参数（如果Grok API支持）
    if edit_request.strength is not None and edit_request.strength != 0.85:
        image_edit_config["strength"] = edit_request.strength
        logger.info(f"使用自定义编辑强度: {edit_request.strength}")

    # 添加编辑模式参数
    if edit_request.edit_mode and edit_request.edit_mode != "comprehensive":
        image_edit_config["editMode"] = edit_request.edit_mode
        logger.info(f"使用编辑模式: {edit_request.edit_mode}")

    # 添加背景保留参数
    if edit_request.preserve_background:
        image_edit_config["preserveBackground"] = True
        logger.info("启用背景保留模式")

    # 添加引导强度参数
    if edit_request.guidance_scale is not None and edit_request.guidance_scale != 7.5:
        image_edit_config["guidanceScale"] = edit_request.guidance_scale
        logger.info(f"使用自定义引导强度: {edit_request.guidance_scale}")

    model_config_override = {
        "modelMap": {
            "imageEditModel": "imagine",
            "imageEditModelConfig": image_edit_config,
        }
    }

    if parent_post_id:
        model_config_override["modelMap"]["imageEditModelConfig"]["parentPostId"] = (
            parent_post_id
        )

    # 优化提示词格式，添加明确的编辑指令前缀
    # 根据编辑模式调整提示词
    optimized_prompt = edit_request.prompt
    if edit_request.edit_mode == "comprehensive":
        # 全面编辑模式：强调所有变化都要实现
        optimized_prompt = f"Comprehensive image edit - Apply ALL changes: {edit_request.prompt}"
    elif edit_request.edit_mode == "aggressive":
        # 激进模式：允许大幅改变
        optimized_prompt = f"Aggressive image transformation: {edit_request.prompt}"
    elif edit_request.edit_mode == "conservative":
        # 保守模式：保留原图特征
        optimized_prompt = f"Conservative edit while preserving original features: {edit_request.prompt}"
    else:
        # 默认：添加编辑指令前缀
        optimized_prompt = f"Edit image: {edit_request.prompt}"

    logger.info(f"优化后的提示词: {optimized_prompt[:100]}...")

    raw_payload = {
        "temporary": bool(get_config("chat.temporary")),
        "modelName": model_info.grok_model,
        "message": optimized_prompt,  # 使用优化后的提示词
        "enableImageGeneration": True,
        "returnImageBytes": False,
        "returnRawGrokInXaiRequest": False,
        "enableImageStreaming": True,
        "imageGenerationCount": edit_request.n,  # 使用用户指定的数量
        "forceConcise": False,
        "toolOverrides": {"imageGen": True},
        "enableSideBySide": True,
        "sendFinalMetadata": True,
        "isReasoning": False,
        "disableTextFollowUps": False,  # 改为False，允许文本跟进以便更好地理解编辑指令
        "responseMetadata": {"modelConfigOverride": model_config_override},
        "disableMemory": False,
        "forceSideBySide": False,
    }

    # 记录完整的payload用于调试
    logger.debug(f"Image edit payload: {raw_payload}")

    # 流式模式
    if edit_request.stream:
        chat_service = GrokChatService()
        response = await chat_service.chat(
            token=token,
            message=edit_request.prompt,
            model=model_info.grok_model,
            mode=None,
            stream=True,
            raw_payload=raw_payload,
        )

        processor = ImageStreamProcessor(
            model_info.model_id,
            token,
            n=edit_request.n,
            response_format=response_format,
        )

        async def _wrap_stream(stream):
            async for chunk in stream:
                yield chunk
            # 消费 token
            try:
                await token_mgr.consume(token, EffortType.HIGH)
            except Exception as e:
                logger.warning(f"Failed to consume token: {e}")

        return StreamingResponse(
            _wrap_stream(processor.process(response)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # 非流式模式
    n = edit_request.n
    calls_needed = (n + 1) // 2

    async def _call_edit_with_retry(max_retries=3):
        """
        带重试机制的图生图调用

        Args:
            max_retries: 最大重试次数，默认3次

        Returns:
            生成的图片列表
        """
        last_error = None

        for retry_count in range(max_retries):
            try:
                # 如果是重试，获取新的 token
                if retry_count > 0:
                    logger.info(f"图生图重试 {retry_count}/{max_retries - 1}，尝试获取新 token...")
                    try:
                        nonlocal token_mgr, token
                        token_mgr, token = await _get_token(edit_request.model)
                        logger.info(f"已切换到新 token: {token[:10]}...")
                    except Exception as token_err:
                        logger.error(f"获取新 token 失败: {token_err}")
                        # 如果获取 token 失败，使用原 token 继续尝试

                chat_service = GrokChatService()
                response = await chat_service.chat(
                    token=token,
                    message=edit_request.prompt,
                    model=model_info.grok_model,
                    mode=None,
                    stream=True,
                    raw_payload=raw_payload,
                )
                processor = ImageCollectProcessor(
                    model_info.model_id, token, response_format=response_format
                )
                images = await processor.process(response)

                # 检查是否有有效图片
                valid_images = [img for img in images if img and img != "error"]
                if valid_images:
                    logger.info(f"图生图成功，获得 {len(valid_images)} 张有效图片")
                    return images
                else:
                    logger.warning(f"图生图返回空结果，尝试 {retry_count + 1}/{max_retries}")
                    last_error = Exception("No valid images returned")

            except Exception as e:
                last_error = e
                logger.error(f"图生图调用失败 (尝试 {retry_count + 1}/{max_retries}): {e}")

                # 如果不是最后一次重试，等待一段时间后继续
                if retry_count < max_retries - 1:
                    wait_time = (retry_count + 1) * 2  # 递增等待时间：2s, 4s, 6s
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)

        # 所有重试都失败
        logger.error(f"图生图在 {max_retries} 次尝试后仍然失败")
        if last_error:
            raise last_error
        return []

    if calls_needed == 1:
        all_images = await _call_edit_with_retry()
    else:
        tasks = [_call_edit_with_retry() for _ in range(calls_needed)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_images = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Concurrent call failed: {result}")
            elif isinstance(result, list):
                all_images.extend(result)

    # 消费 token
    try:
        await token_mgr.consume(token, EffortType.HIGH)
    except Exception as e:
        logger.warning(f"Failed to consume token: {e}")

    # 选择图片
    logger.info(f"图生图收集到的图片数量: {len(all_images)}, 请求数量: {n}")
    if len(all_images) >= n:
        selected_images = random.sample(all_images, n)
    else:
        selected_images = all_images.copy()
        while len(selected_images) < n:
            selected_images.append("error")
    logger.info(f"图生图选择的图片数量: {len(selected_images)}, 包含error: {selected_images.count('error')}")

    # 图片已由客户端本地存储，服务端不再保存

    data = [{response_field: img} for img in selected_images]

    return JSONResponse(
        content={
            "created": int(time.time()),
            "data": data,
            "usage": {
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            },
        }
    )

