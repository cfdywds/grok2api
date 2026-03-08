"""
Novel Director - 小说场景导演模块

实现小说转视频时的人物角色一致性管理。
核心思路：角色档案 + 参考图锚定 + Prompt 组装。
"""

from .models import CharacterProfile, Scene, StoryProject
from .service import NovelDirectorService, get_novel_director_service

__all__ = [
    "CharacterProfile",
    "Scene",
    "StoryProject",
    "NovelDirectorService",
    "get_novel_director_service",
]
