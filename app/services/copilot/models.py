"""
Copilot 数据模型
"""

import time
import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


class CopilotMessage(BaseModel):
    """单条对话消息"""

    role: str = Field(..., description="消息角色: user / assistant")
    content: str = Field(..., description="消息文本内容")
    image_urls: List[str] = Field(default_factory=list, description="本轮生成的图片 URL")
    image_prompt: Optional[str] = Field(None, description="使用的英文图片 Prompt")
    timestamp: float = Field(default_factory=time.time)


class CopilotSession(BaseModel):
    """对话会话"""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = Field("", description="会话标题（从首条消息自动生成）")
    messages: List[CopilotMessage] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class CopilotChatRequest(BaseModel):
    """Copilot 对话请求（兼容 OpenAI chat/completions 格式）"""

    model: str = Field("copilot", description="模型名称")
    messages: List[dict] = Field(..., description="OpenAI 格式消息列表")
    stream: Optional[bool] = Field(True, description="是否流式输出")
    session_id: Optional[str] = Field(None, description="会话 ID，不传则新建")

    model_config = {"extra": "ignore"}
