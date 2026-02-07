"""
图片管理服务数据模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    """图片元数据"""
    id: str = Field(..., description="图片唯一标识符")
    filename: str = Field(..., description="文件名")
    prompt: str = Field(..., description="生成提示词")
    model: str = Field(default="grok-imagine-1.0", description="使用的模型")
    aspect_ratio: str = Field(default="1:1", description="宽高比")
    created_at: int = Field(..., description="创建时间戳（毫秒）")
    file_size: Optional[int] = Field(None, description="文件大小（字节）")
    width: Optional[int] = Field(None, description="图片宽度")
    height: Optional[int] = Field(None, description="图片高度")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    nsfw: bool = Field(default=False, description="是否为敏感内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")
    quality_score: Optional[float] = Field(None, description="图片质量综合评分（0-100）")
    blur_score: Optional[float] = Field(None, description="模糊度分数（越高越清晰）")
    brightness_score: Optional[float] = Field(None, description="亮度分数（0-100，50为正常）")
    quality_issues: List[str] = Field(default_factory=list, description="质量问题列表")


class ImageFilter(BaseModel):
    """图片筛选条件"""
    search: Optional[str] = Field(None, description="搜索关键词（提示词）")
    model: Optional[str] = Field(None, description="模型筛选")
    aspect_ratio: Optional[str] = Field(None, description="宽高比筛选")
    tags: Optional[List[str]] = Field(None, description="标签筛选")
    start_date: Optional[int] = Field(None, description="开始日期（时间戳）")
    end_date: Optional[int] = Field(None, description="结束日期（时间戳）")
    nsfw: Optional[bool] = Field(None, description="是否筛选敏感内容")
    min_quality_score: Optional[float] = Field(None, description="最低质量分数筛选")
    max_quality_score: Optional[float] = Field(None, description="最高质量分数筛选")
    has_quality_issues: Optional[bool] = Field(None, description="是否筛选有质量问题的图片")


class ImageListResponse(BaseModel):
    """图片列表响应"""
    images: List[ImageMetadata] = Field(..., description="图片列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")


class ImageStats(BaseModel):
    """图片统计信息"""
    total_count: int = Field(0, description="图片总数")
    total_size: int = Field(0, description="总文件大小（字节）")
    month_count: int = Field(0, description="本月新增数量")
    top_tags: List[Dict[str, Any]] = Field(default_factory=list, description="常用标签")
    models: Dict[str, int] = Field(default_factory=dict, description="模型分布")
    aspect_ratios: Dict[str, int] = Field(default_factory=dict, description="宽高比分布")
