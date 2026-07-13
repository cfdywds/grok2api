"""
Copilot 图片助手 API 路由

提供对话式图片生成和会话管理接口
"""

import time
from typing import Optional

import orjson
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.config import get_config
from app.core.exceptions import AppException, ValidationException, ErrorType
from app.core.logger import logger
from app.services.copilot.service import get_copilot_service
from app.services.copilot.models import CopilotChatRequest


router = APIRouter(tags=["Copilot"])


# ==================== 对话接口 ====================


@router.post("/copilot/chat")
async def copilot_chat(request: CopilotChatRequest):
    """
    Copilot 对话接口

    自动识别用户意图：
    - 普通聊天 → 直接回复
    - 图片需求 → 生成专业 Prompt → 调用 Grok 生成图片 → 返回 Markdown 图片链接
    """
    # 检查功能是否启用
    if not get_config("copilot.enabled", True):
        raise AppException(
            message="Copilot 功能未启用",
            error_type=ErrorType.SERVICE_UNAVAILABLE.value,
            status_code=503,
        )

    # 提取最后一条用户消息
    user_message = ""
    for msg in reversed(request.messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                user_message = content
            elif isinstance(content, list):
                # 支持 OpenAI 多模态格式
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        user_message = block.get("text", "")
                        break
            break

    if not user_message:
        raise ValidationException(
            message="消息内容不能为空",
            param="messages",
            code="empty_content",
        )

    service = get_copilot_service()

    try:
        session_id, result = await service.chat(
            session_id=request.session_id,
            user_message=user_message,
            stream=request.stream,
        )
    except ConnectionError as e:
        raise AppException(
            message=str(e),
            error_type=ErrorType.SERVICE_UNAVAILABLE.value,
            status_code=503,
        )

    if request.stream:
        # 流式响应 - OpenAI SSE 格式
        async def sse_generator():
            try:
                async for token in result:
                    chunk = {
                        "id": f"chatcmpl-copilot-{session_id}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "copilot",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None,
                            }
                        ],
                        "session_id": session_id,
                    }
                    yield f"data: {orjson.dumps(chunk).decode()}\n\n"

                # 发送结束标记
                final_chunk = {
                    "id": f"chatcmpl-copilot-{session_id}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "copilot",
                    "choices": [
                        {"index": 0, "delta": {}, "finish_reason": "stop"}
                    ],
                    "session_id": session_id,
                }
                yield f"data: {orjson.dumps(final_chunk).decode()}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Copilot SSE error: {e}")
                error_chunk = {
                    "error": {"message": str(e), "type": "server_error"}
                }
                yield f"data: {orjson.dumps(error_chunk).decode()}\n\n"

        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        # 非流式响应 - OpenAI 格式
        return JSONResponse(
            content={
                "id": f"chatcmpl-copilot-{session_id}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "copilot",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": result},
                        "finish_reason": "stop",
                    }
                ],
                "session_id": session_id,
            }
        )


# ==================== 会话管理接口 ====================


@router.get("/copilot/sessions")
async def list_sessions():
    """列出所有 Copilot 会话"""
    service = get_copilot_service()
    sessions = await service.memory.list_sessions()
    return JSONResponse(content={"sessions": sessions})


@router.get("/copilot/sessions/{session_id}")
async def get_session(session_id: str):
    """获取指定会话的完整历史"""
    service = get_copilot_service()
    session = await service.memory.get_session(session_id)
    if not session:
        raise AppException(
            message=f"会话 {session_id} 不存在",
            error_type=ErrorType.NOT_FOUND.value,
            status_code=404,
        )
    return JSONResponse(content=session.model_dump())


@router.delete("/copilot/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    service = get_copilot_service()
    deleted = await service.memory.delete_session(session_id)
    if not deleted:
        raise AppException(
            message=f"会话 {session_id} 不存在",
            error_type=ErrorType.NOT_FOUND.value,
            status_code=404,
        )
    return JSONResponse(content={"deleted": True, "session_id": session_id})
