"""
Novel Director 数据模型

定义角色档案、场景、故事项目的 Pydantic 模型。
"""

import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class CharacterProfile(BaseModel):
    """角色档案"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="角色名")
    appearance: str = Field(default="", description="外貌描述（英文，用于 prompt）")
    personality: str = Field(default="", description="性格描述（中文，用户参考）")
    traits: List[str] = Field(default_factory=list, description="特征标签")
    reference_image_id: Optional[str] = Field(default=None, description="关联的图片 ID")
    reference_image_url: Optional[str] = Field(default=None, description="参考图 URL")
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)


class CharacterCreate(BaseModel):
    """创建角色请求"""

    name: str = Field(..., min_length=1, max_length=50)
    appearance: str = Field(default="", max_length=500)
    personality: str = Field(default="", max_length=500)
    traits: List[str] = Field(default_factory=list)
    reference_image_id: Optional[str] = None
    reference_image_url: Optional[str] = None


class CharacterUpdate(BaseModel):
    """更新角色请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    appearance: Optional[str] = Field(None, max_length=500)
    personality: Optional[str] = Field(None, max_length=500)
    traits: Optional[List[str]] = None
    reference_image_id: Optional[str] = None
    reference_image_url: Optional[str] = None


class Scene(BaseModel):
    """场景"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = Field(..., description="所属项目 ID")
    order: int = Field(default=0, description="场景顺序")
    narrative: str = Field(default="", description="场景叙事文本")
    characters: List[str] = Field(default_factory=list, description="出场角色 ID 列表")
    setting: str = Field(default="", description="场景环境描述")
    mood: str = Field(default="", description="情绪氛围")
    camera: str = Field(default="", description="镜头语言")
    generated_video_id: Optional[str] = Field(default=None, description="生成的视频 ID")
    generated_video_url: Optional[str] = Field(default=None, description="生成的视频 URL")
    prompt_used: Optional[str] = Field(default=None, description="实际使用的 prompt")
    status: str = Field(default="draft", description="状态: draft/ready/generating/done")
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)


class SceneCreate(BaseModel):
    """创建场景请求"""

    project_id: str
    order: int = 0
    narrative: str = Field(default="", max_length=2000)
    characters: List[str] = Field(default_factory=list)
    setting: str = Field(default="", max_length=500)
    mood: str = Field(default="")
    camera: str = Field(default="")


class SceneUpdate(BaseModel):
    """更新场景请求"""

    order: Optional[int] = None
    narrative: Optional[str] = Field(None, max_length=2000)
    characters: Optional[List[str]] = None
    setting: Optional[str] = Field(None, max_length=500)
    mood: Optional[str] = None
    camera: Optional[str] = None
    generated_video_id: Optional[str] = None
    generated_video_url: Optional[str] = None
    prompt_used: Optional[str] = None
    status: Optional[str] = None


class StoryProject(BaseModel):
    """故事项目"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(..., description="项目名称")
    description: str = Field(default="", description="故事简介")
    style_preset: str = Field(default="normal", description="默认风格")
    aspect_ratio: str = Field(default="16:9", description="默认比例")
    resolution: str = Field(default="720p", description="默认分辨率")
    scenes: List[str] = Field(default_factory=list, description="场景 ID 列表")
    characters: List[str] = Field(default_factory=list, description="角色 ID 列表")
    created_at: int = Field(default=0)
    updated_at: int = Field(default=0)


class ProjectCreate(BaseModel):
    """创建项目请求"""

    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    style_preset: str = Field(default="normal")
    aspect_ratio: str = Field(default="16:9")
    resolution: str = Field(default="720p")


class ProjectUpdate(BaseModel):
    """更新项目请求"""

    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    style_preset: Optional[str] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None


class ReorderScenesRequest(BaseModel):
    """重排序场景请求"""

    project_id: str
    scene_ids: List[str]


class BuildPromptRequest(BaseModel):
    """构建 Prompt 请求"""

    style_preset: Optional[str] = None
    include_narrative: bool = True


__all__ = [
    "CharacterProfile",
    "CharacterCreate",
    "CharacterUpdate",
    "Scene",
    "SceneCreate",
    "SceneUpdate",
    "StoryProject",
    "ProjectCreate",
    "ProjectUpdate",
    "ReorderScenesRequest",
    "BuildPromptRequest",
]
