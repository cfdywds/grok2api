"""
视频管理服务数据模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """视频元数据"""
    id: str = Field(..., description="视频唯一标识符")
    filename: str = Field(..., description="文件名")
    prompt: str = Field(default="", description="生成提示词")
    model: str = Field(default="grok-imagine-1.0-video", description="使用的模型")
    aspect_ratio: str = Field(default="3:2", description="宽高比")
    video_length: int = Field(default=6, description="视频时长（秒）")
    resolution: str = Field(default="480p", description="分辨率")
    preset: str = Field(default="normal", description="预设风格")
    created_at: int = Field(..., description="创建时间戳（毫秒）")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    favorite: bool = Field(default=False, description="是否收藏")
    thumbnail_filename: Optional[str] = Field(None, description="缩略图文件名")
    video_post_id: Optional[str] = Field(None, description="Grok 视频 post ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class VideoFilter(BaseModel):
    """视频筛选条件"""
    search: Optional[str] = Field(None, description="搜索关键词（提示词）")
    model: Optional[str] = Field(None, description="模型筛选")
    aspect_ratio: Optional[str] = Field(None, description="宽高比筛选")
    video_length: Optional[int] = Field(None, description="视频时长筛选（6/10/15）")
    resolution: Optional[str] = Field(None, description="分辨率筛选（480p/720p）")
    preset: Optional[str] = Field(None, description="预设风格筛选")
    tags: Optional[List[str]] = Field(None, description="标签筛选")
    start_date: Optional[int] = Field(None, description="开始日期（时间戳）")
    end_date: Optional[int] = Field(None, description="结束日期（时间戳）")
    favorite: Optional[bool] = Field(None, description="是否筛选收藏的视频")


class VideoListResponse(BaseModel):
    """视频列表响应"""
    videos: List[VideoMetadata] = Field(..., description="视频列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")


class VideoStats(BaseModel):
    """视频统计信息"""
    total_count: int = Field(0, description="视频总数")
    total_size: int = Field(0, description="总文件大小（字节）")
    month_count: int = Field(0, description="本月新增数量")
    top_tags: List[Dict[str, Any]] = Field(default_factory=list, description="常用标签")
    resolutions: Dict[str, int] = Field(default_factory=dict, description="分辨率分布")
    presets: Dict[str, int] = Field(default_factory=dict, description="预设风格分布")
    aspect_ratios: Dict[str, int] = Field(default_factory=dict, description="宽高比分布")
