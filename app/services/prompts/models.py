"""提示词数据模型"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Prompt(BaseModel):
    """提示词模型"""
    id: str = Field(..., description="提示词 ID")
    title: str = Field(..., description="提示词标题")
    content: str = Field(..., description="提示词内容")
    category: str = Field(default="默认", description="分类")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    favorite: bool = Field(default=False, description="是否收藏")
    use_count: int = Field(default=0, description="使用次数")
    created_at: int = Field(..., description="创建时间（毫秒时间戳）")
    updated_at: int = Field(..., description="更新时间（毫秒时间戳）")


class PromptCreate(BaseModel):
    """创建提示词请求"""
    title: str = Field(..., min_length=1, max_length=100, description="提示词标题")
    content: str = Field(..., min_length=1, description="提示词内容")
    category: str = Field(default="默认", description="分类")
    tags: List[str] = Field(default_factory=list, description="标签列表")


class PromptUpdate(BaseModel):
    """更新提示词请求"""
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="提示词标题")
    content: Optional[str] = Field(None, min_length=1, description="提示词内容")
    category: Optional[str] = Field(None, description="分类")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    favorite: Optional[bool] = Field(None, description="是否收藏")


class PromptList(BaseModel):
    """提示词列表响应"""
    prompts: List[Prompt]
    total: int
    categories: List[str]
    tags: List[str]
