"""提示词管理服务"""
import uuid
import time
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.core.logger import logger
from app.core.storage import StorageFactory
from .models import Prompt, PromptCreate, PromptUpdate, PromptList


class PromptService:
    """提示词管理服务"""

    def __init__(self):
        self.storage = StorageFactory.get_storage()

    async def get_all_prompts(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        favorite: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> PromptList:
        """获取所有提示词"""
        try:
            data = await self.storage.load_prompts()
            if not data:
                data = {"prompts": [], "version": "1.0"}

            prompts = [Prompt(**p) for p in data.get("prompts", [])]

            # 筛选
            if category:
                prompts = [p for p in prompts if p.category == category]
            if tag:
                prompts = [p for p in prompts if tag in p.tags]
            if favorite is not None:
                prompts = [p for p in prompts if p.favorite == favorite]
            if search:
                search_lower = search.lower()
                prompts = [
                    p for p in prompts
                    if search_lower in p.title.lower()
                    or search_lower in p.content.lower()
                    or any(search_lower in t.lower() for t in p.tags)
                ]

            # 按更新时间倒序排序
            prompts.sort(key=lambda x: x.updated_at, reverse=True)

            # 统计分类和标签
            categories = list(set(p.category for p in prompts))
            all_tags = []
            for p in prompts:
                all_tags.extend(p.tags)
            tags = list(set(all_tags))

            return PromptList(
                prompts=prompts,
                total=len(prompts),
                categories=sorted(categories),
                tags=sorted(tags),
            )
        except Exception as e:
            logger.error(f"获取提示词列表失败: {e}")
            return PromptList(prompts=[], total=0, categories=[], tags=[])

    async def get_prompt(self, prompt_id: str) -> Optional[Prompt]:
        """获取单个提示词"""
        try:
            data = await self.storage.load_prompts()
            if not data:
                return None

            for p in data.get("prompts", []):
                if p.get("id") == prompt_id:
                    return Prompt(**p)
            return None
        except Exception as e:
            logger.error(f"获取提示词失败: {e}")
            return None

    async def create_prompt(self, prompt_data: PromptCreate) -> Prompt:
        """创建提示词"""
        try:
            data = await self.storage.load_prompts()
            if not data:
                data = {"prompts": [], "version": "1.0"}

            now = int(time.time() * 1000)
            prompt = Prompt(
                id=str(uuid.uuid4()),
                title=prompt_data.title,
                content=prompt_data.content,
                category=prompt_data.category,
                tags=prompt_data.tags,
                favorite=False,
                use_count=0,
                created_at=now,
                updated_at=now,
            )

            data["prompts"].append(prompt.model_dump())
            await self.storage.save_prompts(data)

            logger.info(f"创建提示词成功: {prompt.id}")
            return prompt
        except Exception as e:
            logger.error(f"创建提示词失败: {e}")
            raise

    async def update_prompt(
        self, prompt_id: str, prompt_data: PromptUpdate
    ) -> Optional[Prompt]:
        """更新提示词"""
        try:
            data = await self.storage.load_prompts()
            if not data:
                return None

            prompts = data.get("prompts", [])
            for i, p in enumerate(prompts):
                if p.get("id") == prompt_id:
                    # 更新字段
                    if prompt_data.title is not None:
                        p["title"] = prompt_data.title
                    if prompt_data.content is not None:
                        p["content"] = prompt_data.content
                    if prompt_data.category is not None:
                        p["category"] = prompt_data.category
                    if prompt_data.tags is not None:
                        p["tags"] = prompt_data.tags
                    if prompt_data.favorite is not None:
                        p["favorite"] = prompt_data.favorite

                    p["updated_at"] = int(time.time() * 1000)
                    prompts[i] = p

                    data["prompts"] = prompts
                    await self.storage.save_prompts(data)

                    logger.info(f"更新提示词成功: {prompt_id}")
                    return Prompt(**p)

            return None
        except Exception as e:
            logger.error(f"更新提示词失败: {e}")
            raise

    async def delete_prompts(self, prompt_ids: List[str]) -> int:
        """删除提示词"""
        try:
            data = await self.storage.load_prompts()
            if not data:
                return 0

            prompts = data.get("prompts", [])
            original_count = len(prompts)

            # 过滤掉要删除的提示词
            prompts = [p for p in prompts if p.get("id") not in prompt_ids]
            deleted_count = original_count - len(prompts)

            data["prompts"] = prompts
            await self.storage.save_prompts(data)

            logger.info(f"删除提示词成功: {deleted_count} 个")
            return deleted_count
        except Exception as e:
            logger.error(f"删除提示词失败: {e}")
            raise

    async def increment_use_count(self, prompt_id: str) -> bool:
        """增加使用次数"""
        try:
            data = await self.storage.load_prompts()
            if not data:
                return False

            prompts = data.get("prompts", [])
            for i, p in enumerate(prompts):
                if p.get("id") == prompt_id:
                    p["use_count"] = p.get("use_count", 0) + 1
                    p["updated_at"] = int(time.time() * 1000)
                    prompts[i] = p

                    data["prompts"] = prompts
                    await self.storage.save_prompts(data)
                    return True

            return False
        except Exception as e:
            logger.error(f"增加使用次数失败: {e}")
            return False

    async def export_prompts(self) -> Dict[str, Any]:
        """导出所有提示词"""
        try:
            data = await self.storage.load_prompts()
            if not data:
                data = {"prompts": [], "version": "1.0"}
            return data
        except Exception as e:
            logger.error(f"导出提示词失败: {e}")
            return {"prompts": [], "version": "1.0"}

    async def import_prompts(self, import_data: Dict[str, Any], merge: bool = True) -> int:
        """导入提示词"""
        try:
            if merge:
                # 合并模式：保留现有数据
                existing_data = await self.storage.load_prompts()
                if not existing_data:
                    existing_data = {"prompts": [], "version": "1.0"}

                existing_ids = {p.get("id") for p in existing_data.get("prompts", [])}
                new_prompts = [
                    p for p in import_data.get("prompts", [])
                    if p.get("id") not in existing_ids
                ]

                existing_data["prompts"].extend(new_prompts)
                await self.storage.save_prompts(existing_data)
                return len(new_prompts)
            else:
                # 覆盖模式：替换所有数据
                await self.storage.save_prompts(import_data)
                return len(import_data.get("prompts", []))
        except Exception as e:
            logger.error(f"导入提示词失败: {e}")
            raise
