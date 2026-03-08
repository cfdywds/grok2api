"""
Novel Director 服务层

提供角色、场景、项目的 CRUD 操作以及 Prompt 组装器。
"""

import time
from typing import Dict, List, Optional

from app.core.logger import logger
from app.core.storage import get_storage
from .models import (
    CharacterProfile,
    CharacterCreate,
    CharacterUpdate,
    Scene,
    SceneCreate,
    SceneUpdate,
    StoryProject,
    ProjectCreate,
    ProjectUpdate,
)


# 情绪氛围映射
MOOD_MAP = {
    "紧张": "tense, dramatic",
    "温馨": "warm, cozy",
    "悲伤": "melancholic, somber",
    "欢快": "cheerful, lively",
    "神秘": "mysterious, enigmatic",
    "浪漫": "romantic, dreamy",
    "恐怖": "horror, eerie",
    "史诗": "epic, grand",
    "平静": "peaceful, serene",
    "激动": "exciting, thrilling",
}

# 镜头语言映射
CAMERA_MAP = {
    "特写": "close-up shot",
    "中景": "medium shot",
    "全景": "wide shot",
    "远景": "extreme wide shot",
    "俯视": "high angle shot",
    "仰视": "low angle shot",
    "跟拍": "tracking shot",
    "摇镜": "panning shot",
    "手持": "handheld shot",
    "定格": "static shot",
}

# 风格预设映射
STYLE_MAP = {
    "fun": "cinematic, vivid colors, dynamic movement",
    "normal": "natural lighting, realistic",
    "spicy": "dramatic lighting, high contrast, stylized",
    "cinematic": "cinematic, film grain, anamorphic lens",
    "anime": "anime style, vibrant colors, detailed",
    "documentary": "documentary style, handheld camera, natural light",
}


class NovelDirectorService:
    """小说场景导演服务"""

    def __init__(self):
        self._storage = get_storage()
        self._data: Optional[Dict] = None

    async def _load_data(self) -> Dict:
        """加载数据"""
        if self._data is None:
            self._data = await self._storage.load_novel_data()
        return self._data

    async def _save_data(self):
        """保存数据"""
        if self._data is not None:
            await self._storage.save_novel_data(self._data)

    def _get_timestamp(self) -> int:
        return int(time.time() * 1000)

    # ==================== 角色管理 ====================

    async def list_characters(self) -> List[CharacterProfile]:
        """获取所有角色"""
        data = await self._load_data()
        return [CharacterProfile(**c) for c in data.get("characters", [])]

    async def get_character(self, character_id: str) -> Optional[CharacterProfile]:
        """获取单个角色"""
        data = await self._load_data()
        for c in data.get("characters", []):
            if c.get("id") == character_id:
                return CharacterProfile(**c)
        return None

    async def create_character(self, req: CharacterCreate) -> CharacterProfile:
        """创建角色"""
        data = await self._load_data()
        now = self._get_timestamp()

        character = CharacterProfile(
            name=req.name,
            appearance=req.appearance,
            personality=req.personality,
            traits=req.traits or [],
            reference_image_id=req.reference_image_id,
            reference_image_url=req.reference_image_url,
            created_at=now,
            updated_at=now,
        )

        if "characters" not in data:
            data["characters"] = []
        data["characters"].append(character.model_dump())
        await self._save_data()

        logger.info(f"NovelDirector: 创建角色 {character.id} - {character.name}")
        return character

    async def update_character(
        self, character_id: str, req: CharacterUpdate
    ) -> Optional[CharacterProfile]:
        """更新角色"""
        data = await self._load_data()

        for i, c in enumerate(data.get("characters", [])):
            if c.get("id") == character_id:
                update_data = req.model_dump(exclude_unset=True)
                update_data["updated_at"] = self._get_timestamp()

                # 合并更新
                c.update(update_data)
                data["characters"][i] = c
                await self._save_data()

                logger.info(f"NovelDirector: 更新角色 {character_id}")
                return CharacterProfile(**c)

        return None

    async def delete_character(self, character_id: str) -> bool:
        """删除角色"""
        data = await self._load_data()

        characters = data.get("characters", [])
        original_len = len(characters)
        data["characters"] = [c for c in characters if c.get("id") != character_id]

        if len(data["characters"]) < original_len:
            # 同时从项目中移除该角色
            for p in data.get("projects", []):
                if character_id in p.get("characters", []):
                    p["characters"].remove(character_id)

            # 从场景中移除该角色
            for s in data.get("scenes", []):
                if character_id in s.get("characters", []):
                    s["characters"].remove(character_id)

            await self._save_data()
            logger.info(f"NovelDirector: 删除角色 {character_id}")
            return True

        return False

    # ==================== 项目管理 ====================

    async def list_projects(self) -> List[StoryProject]:
        """获取所有项目"""
        data = await self._load_data()
        return [StoryProject(**p) for p in data.get("projects", [])]

    async def get_project(self, project_id: str) -> Optional[StoryProject]:
        """获取单个项目"""
        data = await self._load_data()
        for p in data.get("projects", []):
            if p.get("id") == project_id:
                return StoryProject(**p)
        return None

    async def create_project(self, req: ProjectCreate) -> StoryProject:
        """创建项目"""
        data = await self._load_data()
        now = self._get_timestamp()

        project = StoryProject(
            title=req.title,
            description=req.description,
            style_preset=req.style_preset,
            aspect_ratio=req.aspect_ratio,
            resolution=req.resolution,
            scenes=[],
            characters=[],
            created_at=now,
            updated_at=now,
        )

        if "projects" not in data:
            data["projects"] = []
        data["projects"].append(project.model_dump())
        await self._save_data()

        logger.info(f"NovelDirector: 创建项目 {project.id} - {project.title}")
        return project

    async def update_project(
        self, project_id: str, req: ProjectUpdate
    ) -> Optional[StoryProject]:
        """更新项目"""
        data = await self._load_data()

        for i, p in enumerate(data.get("projects", [])):
            if p.get("id") == project_id:
                update_data = req.model_dump(exclude_unset=True)
                update_data["updated_at"] = self._get_timestamp()

                p.update(update_data)
                data["projects"][i] = p
                await self._save_data()

                logger.info(f"NovelDirector: 更新项目 {project_id}")
                return StoryProject(**p)

        return None

    async def delete_project(self, project_id: str) -> bool:
        """删除项目及其所有场景"""
        data = await self._load_data()

        # 获取项目的所有场景 ID
        scene_ids = set()
        for p in data.get("projects", []):
            if p.get("id") == project_id:
                scene_ids = set(p.get("scenes", []))
                break

        # 删除项目
        projects = data.get("projects", [])
        original_len = len(projects)
        data["projects"] = [p for p in projects if p.get("id") != project_id]

        if len(data["projects"]) < original_len:
            # 删除关联场景
            data["scenes"] = [
                s for s in data.get("scenes", []) if s.get("id") not in scene_ids
            ]
            await self._save_data()
            logger.info(f"NovelDirector: 删除项目 {project_id} 及 {len(scene_ids)} 个场景")
            return True

        return False

    # ==================== 场景管理 ====================

    async def list_scenes(self, project_id: str) -> List[Scene]:
        """获取项目的所有场景"""
        data = await self._load_data()
        scenes = []
        for s in data.get("scenes", []):
            if s.get("project_id") == project_id:
                scenes.append(Scene(**s))
        # 按 order 排序
        scenes.sort(key=lambda x: x.order)
        return scenes

    async def get_scene(self, scene_id: str) -> Optional[Scene]:
        """获取单个场景"""
        data = await self._load_data()
        for s in data.get("scenes", []):
            if s.get("id") == scene_id:
                return Scene(**s)
        return None

    async def create_scene(self, req: SceneCreate) -> Scene:
        """创建场景"""
        data = await self._load_data()
        now = self._get_timestamp()

        # 计算场景顺序
        existing_scenes = [
            s for s in data.get("scenes", []) if s.get("project_id") == req.project_id
        ]
        max_order = max([s.get("order", 0) for s in existing_scenes], default=-1)

        scene = Scene(
            project_id=req.project_id,
            order=req.order if req.order > 0 else max_order + 1,
            narrative=req.narrative,
            characters=req.characters or [],
            setting=req.setting,
            mood=req.mood,
            camera=req.camera,
            created_at=now,
            updated_at=now,
        )

        if "scenes" not in data:
            data["scenes"] = []
        data["scenes"].append(scene.model_dump())

        # 更新项目的 scenes 列表
        for p in data.get("projects", []):
            if p.get("id") == req.project_id:
                if "scenes" not in p:
                    p["scenes"] = []
                p["scenes"].append(scene.id)
                p["updated_at"] = now
                break

        await self._save_data()

        logger.info(f"NovelDirector: 创建场景 {scene.id} (项目 {req.project_id})")
        return scene

    async def update_scene(self, scene_id: str, req: SceneUpdate) -> Optional[Scene]:
        """更新场景"""
        data = await self._load_data()

        for i, s in enumerate(data.get("scenes", [])):
            if s.get("id") == scene_id:
                update_data = req.model_dump(exclude_unset=True)
                update_data["updated_at"] = self._get_timestamp()

                s.update(update_data)
                data["scenes"][i] = s
                await self._save_data()

                logger.info(f"NovelDirector: 更新场景 {scene_id}")
                return Scene(**s)

        return None

    async def delete_scene(self, scene_id: str) -> bool:
        """删除场景"""
        data = await self._load_data()

        # 获取场景的 project_id
        scene_project_id = None
        for s in data.get("scenes", []):
            if s.get("id") == scene_id:
                scene_project_id = s.get("project_id")
                break

        scenes = data.get("scenes", [])
        original_len = len(scenes)
        data["scenes"] = [s for s in scenes if s.get("id") != scene_id]

        if len(data["scenes"]) < original_len:
            # 从项目中移除场景引用
            if scene_project_id:
                for p in data.get("projects", []):
                    if p.get("id") == scene_project_id:
                        if scene_id in p.get("scenes", []):
                            p["scenes"].remove(scene_id)
                        break

            await self._save_data()
            logger.info(f"NovelDirector: 删除场景 {scene_id}")
            return True

        return False

    async def reorder_scenes(self, project_id: str, scene_ids: List[str]) -> bool:
        """重排序场景"""
        data = await self._load_data()

        # 更新场景顺序
        for i, sid in enumerate(scene_ids):
            for s in data.get("scenes", []):
                if s.get("id") == sid and s.get("project_id") == project_id:
                    s["order"] = i
                    s["updated_at"] = self._get_timestamp()
                    break

        # 更新项目的 scenes 列表
        for p in data.get("projects", []):
            if p.get("id") == project_id:
                p["scenes"] = scene_ids
                p["updated_at"] = self._get_timestamp()
                break

        await self._save_data()
        logger.info(f"NovelDirector: 重排序项目 {project_id} 的场景")
        return True

    # ==================== Prompt 组装器 ====================

    def build_prompt(
        self,
        scene: Scene,
        characters: List[CharacterProfile],
        style_preset: str = "normal",
        include_narrative: bool = True,
    ) -> str:
        """
        组装场景 Prompt

        模板: [场景描述] + [角色外貌] + [环境/光线/镜头] + [风格标签]
        """
        parts = []

        # 1. 叙事文本（可选）
        if include_narrative and scene.narrative:
            parts.append(scene.narrative)

        # 2. 环境描述
        if scene.setting:
            parts.append(scene.setting)

        # 3. 角色外貌（拼接所有出场角色的 appearance）
        char_descriptions = []
        for char in characters:
            if char.appearance:
                char_descriptions.append(char.appearance)
        if char_descriptions:
            parts.append(", ".join(char_descriptions))

        # 4. 情绪氛围
        if scene.mood:
            mood_en = MOOD_MAP.get(scene.mood, scene.mood)
            parts.append(f"{mood_en} atmosphere")

        # 5. 镜头语言
        if scene.camera:
            camera_en = CAMERA_MAP.get(scene.camera, scene.camera)
            parts.append(camera_en)

        # 6. 风格标签
        style_en = STYLE_MAP.get(style_preset, "cinematic, high quality")
        parts.append(style_en)

        return ". ".join(parts) + "."

    async def build_scene_prompt(
        self,
        scene_id: str,
        style_preset: Optional[str] = None,
        include_narrative: bool = True,
    ) -> Optional[str]:
        """构建场景的完整 Prompt"""
        scene = await self.get_scene(scene_id)
        if not scene:
            return None

        # 获取项目以使用默认风格
        project = await self.get_project(scene.project_id)
        final_style = style_preset or (project.style_preset if project else "normal")

        # 获取场景中的角色
        characters = []
        for char_id in scene.characters:
            char = await self.get_character(char_id)
            if char:
                characters.append(char)

        return self.build_prompt(scene, characters, final_style, include_narrative)

    async def get_scene_reference_image(self, scene_id: str) -> Optional[str]:
        """获取场景的第一个角色的参考图 URL"""
        scene = await self.get_scene(scene_id)
        if not scene or not scene.characters:
            return None

        for char_id in scene.characters:
            char = await self.get_character(char_id)
            if char and char.reference_image_url:
                return char.reference_image_url

        return None


# 单例服务
_novel_director_service: Optional[NovelDirectorService] = None


def get_novel_director_service() -> NovelDirectorService:
    """获取 NovelDirectorService 单例"""
    global _novel_director_service
    if _novel_director_service is None:
        _novel_director_service = NovelDirectorService()
    return _novel_director_service
