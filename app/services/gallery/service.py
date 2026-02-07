"""
图片元数据管理服务
"""

import os
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

from app.core.storage import get_storage
from app.core.logger import logger
from .models import ImageMetadata, ImageListResponse, ImageFilter, ImageStats


class ImageMetadataService:
    """图片元数据管理服务"""

    def __init__(self):
        self.storage = get_storage()
        self.image_dir = Path(__file__).parent.parent.parent.parent / "data" / "tmp" / "image"

    async def add_image(self, metadata: ImageMetadata) -> bool:
        """
        添加图片元数据

        Args:
            metadata: 图片元数据

        Returns:
            是否添加成功
        """
        try:
            async with self.storage.acquire_lock("image_metadata", timeout=10):
                data = await self.storage.load_image_metadata()

                # 检查是否已存在
                existing_ids = {img["id"] for img in data.get("images", [])}
                if metadata.id in existing_ids:
                    logger.warning(f"图片元数据已存在: {metadata.id}")
                    return False

                # 添加新元数据
                data.setdefault("images", []).append(metadata.model_dump())

                # 保存
                await self.storage.save_image_metadata(data)
                logger.info(f"添加图片元数据成功: {metadata.id}")
                return True

        except Exception as e:
            logger.error(f"添加图片元数据失败: {e}")
            return False

    async def get_image(self, image_id: str) -> Optional[ImageMetadata]:
        """
        获取图片详情

        Args:
            image_id: 图片ID

        Returns:
            图片元数据，不存在返回 None
        """
        try:
            data = await self.storage.load_image_metadata()

            for img in data.get("images", []):
                if img.get("id") == image_id:
                    return ImageMetadata(**img)

            return None

        except Exception as e:
            logger.error(f"获取图片详情失败: {e}")
            return None

    async def list_images(
        self,
        filters: Optional[ImageFilter] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> ImageListResponse:
        """
        列出图片（支持筛选、分页、排序）

        Args:
            filters: 筛选条件
            page: 页码（从1开始）
            page_size: 每页数量
            sort_by: 排序字段
            sort_order: 排序顺序（asc/desc）

        Returns:
            图片列表响应
        """
        try:
            data = await self.storage.load_image_metadata()
            images = data.get("images", [])

            # 应用筛选
            if filters:
                images = self._apply_filters(images, filters)

            # 排序
            reverse = sort_order.lower() == "desc"
            images.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)

            # 分页
            total = len(images)
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            start = (page - 1) * page_size
            end = start + page_size
            page_images = images[start:end]

            # 转换为模型
            image_models = [ImageMetadata(**img) for img in page_images]

            return ImageListResponse(
                images=image_models,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )

        except Exception as e:
            logger.error(f"列出图片失败: {e}")
            return ImageListResponse(
                images=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0
            )

    def _apply_filters(self, images: List[Dict], filters: ImageFilter) -> List[Dict]:
        """应用筛选条件"""
        filtered = images

        # 搜索关键词
        if filters.search:
            search_lower = filters.search.lower()
            filtered = [
                img for img in filtered
                if search_lower in img.get("prompt", "").lower()
            ]

        # 模型筛选
        if filters.model:
            filtered = [
                img for img in filtered
                if img.get("model") == filters.model
            ]

        # 宽高比筛选
        if filters.aspect_ratio:
            filtered = [
                img for img in filtered
                if img.get("aspect_ratio") == filters.aspect_ratio
            ]

        # 标签筛选
        if filters.tags:
            filtered = [
                img for img in filtered
                if any(tag in img.get("tags", []) for tag in filters.tags)
            ]

        # 日期范围筛选
        if filters.start_date:
            filtered = [
                img for img in filtered
                if img.get("created_at", 0) >= filters.start_date
            ]

        if filters.end_date:
            filtered = [
                img for img in filtered
                if img.get("created_at", 0) <= filters.end_date
            ]

        # NSFW 筛选
        if filters.nsfw is not None:
            filtered = [
                img for img in filtered
                if img.get("nsfw", False) == filters.nsfw
            ]

        return filtered

    async def delete_images(self, image_ids: List[str]) -> Dict[str, Any]:
        """
        批量删除图片（文件+元数据）

        Args:
            image_ids: 图片ID列表

        Returns:
            删除结果统计
        """
        deleted_count = 0
        failed_count = 0

        try:
            async with self.storage.acquire_lock("image_metadata", timeout=10):
                data = await self.storage.load_image_metadata()
                images = data.get("images", [])

                # 找到要删除的图片
                to_delete = []
                remaining = []

                for img in images:
                    if img.get("id") in image_ids:
                        to_delete.append(img)
                    else:
                        remaining.append(img)

                # 删除文件
                for img in to_delete:
                    try:
                        file_path = self.image_dir / img.get("filename", "")
                        if file_path.exists():
                            file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除图片文件失败 {img.get('id')}: {e}")
                        failed_count += 1

                # 更新元数据
                data["images"] = remaining
                await self.storage.save_image_metadata(data)

                logger.info(f"批量删除图片: 成功 {deleted_count}, 失败 {failed_count}")

        except Exception as e:
            logger.error(f"批量删除图片失败: {e}")

        return {
            "deleted": deleted_count,
            "failed": failed_count,
            "total": len(image_ids)
        }

    async def update_tags(self, image_id: str, tags: List[str]) -> bool:
        """
        更新图片标签

        Args:
            image_id: 图片ID
            tags: 新标签列表

        Returns:
            是否更新成功
        """
        try:
            async with self.storage.acquire_lock("image_metadata", timeout=10):
                data = await self.storage.load_image_metadata()
                images = data.get("images", [])

                # 查找并更新
                found = False
                for img in images:
                    if img.get("id") == image_id:
                        img["tags"] = tags
                        found = True
                        break

                if not found:
                    logger.warning(f"图片不存在: {image_id}")
                    return False

                # 保存
                await self.storage.save_image_metadata(data)
                logger.info(f"更新图片标签成功: {image_id}")
                return True

        except Exception as e:
            logger.error(f"更新图片标签失败: {e}")
            return False

    async def get_all_tags(self) -> List[Dict[str, Any]]:
        """
        获取所有标签及其使用次数

        Returns:
            标签列表，按使用次数降序排序
        """
        try:
            data = await self.storage.load_image_metadata()
            images = data.get("images", [])

            # 统计标签
            tag_counts = {}
            for img in images:
                for tag in img.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # 转换为列表并排序
            tags = [
                {"name": tag, "count": count}
                for tag, count in tag_counts.items()
            ]
            tags.sort(key=lambda x: x["count"], reverse=True)

            return tags

        except Exception as e:
            logger.error(f"获取标签列表失败: {e}")
            return []

    async def get_stats(self) -> ImageStats:
        """
        获取统计信息

        Returns:
            统计信息
        """
        try:
            data = await self.storage.load_image_metadata()
            images = data.get("images", [])

            # 总数和总大小
            total_count = len(images)
            total_size = sum(img.get("file_size", 0) for img in images)

            # 本月新增
            now = datetime.now()
            month_start = datetime(now.year, now.month, 1)
            month_start_ts = int(month_start.timestamp() * 1000)
            month_count = sum(
                1 for img in images
                if img.get("created_at", 0) >= month_start_ts
            )

            # 常用标签（前10）
            tag_counts = {}
            for img in images:
                for tag in img.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            top_tags = [
                {"name": tag, "count": count}
                for tag, count in sorted(
                    tag_counts.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            ]

            # 模型分布
            models = {}
            for img in images:
                model = img.get("model", "unknown")
                models[model] = models.get(model, 0) + 1

            # 宽高比分布
            aspect_ratios = {}
            for img in images:
                ratio = img.get("aspect_ratio", "unknown")
                aspect_ratios[ratio] = aspect_ratios.get(ratio, 0) + 1

            return ImageStats(
                total_count=total_count,
                total_size=total_size,
                month_count=month_count,
                top_tags=top_tags,
                models=models,
                aspect_ratios=aspect_ratios
            )

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return ImageStats()

    async def cleanup_orphaned_metadata(self) -> int:
        """
        清理孤立的元数据（文件不存在但元数据存在）

        Returns:
            清理的数量
        """
        try:
            async with self.storage.acquire_lock("image_metadata", timeout=10):
                data = await self.storage.load_image_metadata()
                images = data.get("images", [])

                # 检查文件是否存在
                valid_images = []
                removed_count = 0

                for img in images:
                    file_path = self.image_dir / img.get("filename", "")
                    if file_path.exists():
                        valid_images.append(img)
                    else:
                        removed_count += 1
                        logger.info(f"清理孤立元数据: {img.get('id')}")

                # 更新元数据
                if removed_count > 0:
                    data["images"] = valid_images
                    await self.storage.save_image_metadata(data)
                    logger.info(f"清理孤立元数据完成: {removed_count} 条")

                return removed_count

        except Exception as e:
            logger.error(f"清理孤立元数据失败: {e}")
            return 0


# 全局单例
_service_instance: Optional[ImageMetadataService] = None


def get_image_metadata_service() -> ImageMetadataService:
    """获取图片元数据服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ImageMetadataService()
    return _service_instance
