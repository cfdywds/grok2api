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
from .backup import get_backup_service


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

                # 检查是否已存在（基于ID）
                existing_ids = {img["id"] for img in data.get("images", [])}
                if metadata.id in existing_ids:
                    logger.warning(f"图片元数据已存在: {metadata.id}")
                    return False

                # 检查是否已存在（基于文件名）
                existing_filenames = {img.get("filename") for img in data.get("images", [])}
                if metadata.filename in existing_filenames:
                    logger.warning(f"图片文件名已存在: {metadata.filename}")
                    return False

                # 检查是否已存在（基于内容哈希）
                content_hash = metadata.metadata.get("content_hash") if metadata.metadata else None
                if content_hash:
                    existing_hashes = {
                        img.get("metadata", {}).get("content_hash")
                        for img in data.get("images", [])
                        if img.get("metadata", {}).get("content_hash")
                    }
                    if content_hash in existing_hashes:
                        logger.warning(f"图片内容已存在（哈希: {content_hash[:16]}...）")
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

    async def find_image_by_hash(self, content_hash: str) -> Optional[ImageMetadata]:
        """
        根据内容哈希查找图片

        Args:
            content_hash: 图片内容的SHA256哈希值

        Returns:
            图片元数据，不存在返回 None
        """
        try:
            data = await self.storage.load_image_metadata()

            for img in data.get("images", []):
                img_hash = img.get("metadata", {}).get("content_hash")
                if img_hash == content_hash:
                    return ImageMetadata(**img)

            return None

        except Exception as e:
            logger.error(f"根据哈希查找图片失败: {e}")
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

            logger.info(f"加载图片总数: {len(images)}")
            logger.info(f"筛选条件: {filters}")

            # 应用筛选
            if filters:
                images = self._apply_filters(images, filters)
                logger.info(f"筛选后图片数量: {len(images)}")

            # 排序
            reverse = sort_order.lower() == "desc"
            images.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)

            # 分页
            total = len(images)
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            start = (page - 1) * page_size
            end = start + page_size
            page_images = images[start:end]

            logger.info(f"分页后: total={total}, page_images={len(page_images)}")

            # 添加文件路径信息
            for img in page_images:
                # 添加完整文件路径
                img["file_path"] = str(self.image_dir / img["filename"])
                # 添加相对路径（更友好）
                img["relative_path"] = f"data/tmp/image/{img['filename']}"

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

        # 快捷筛选：低质量图片（分数<40）
        if filters.low_quality:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("quality_score") is not None and img.get("quality_score") < 40
            ]
            logger.info(f"low_quality=True 筛选: {before_count} -> {len(filtered)}")

        # 质量等级快捷筛选
        if filters.quality_level:
            quality_ranges = {
                "excellent": (90, 100),
                "good": (70, 89),
                "fair": (40, 69),
                "poor": (20, 39),
                "very_poor": (0, 19),
                "low_quality": (0, 39)  # 新增：低质量（<40）
            }
            if filters.quality_level in quality_ranges:
                min_score, max_score = quality_ranges[filters.quality_level]
                before_count = len(filtered)
                filtered = [
                    img for img in filtered
                    if img.get("quality_score") is not None and min_score <= img.get("quality_score") <= max_score
                ]
                logger.info(f"quality_level={filters.quality_level} 筛选: {before_count} -> {len(filtered)}")

        # 质量分数筛选
        if filters.min_quality_score is not None:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("quality_score") is not None and img.get("quality_score") >= filters.min_quality_score
            ]
            logger.info(f"min_quality_score={filters.min_quality_score} 筛选: {before_count} -> {len(filtered)}")

        if filters.max_quality_score is not None:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("quality_score") is not None and img.get("quality_score") < filters.max_quality_score
            ]
            logger.info(f"max_quality_score={filters.max_quality_score} 筛选: {before_count} -> {len(filtered)}")

        # 模糊度筛选
        if filters.min_blur_score is not None:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("blur_score") is not None and img.get("blur_score") >= filters.min_blur_score
            ]
            logger.info(f"min_blur_score={filters.min_blur_score} 筛选: {before_count} -> {len(filtered)}")

        if filters.max_blur_score is not None:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("blur_score") is not None and img.get("blur_score") <= filters.max_blur_score
            ]
            logger.info(f"max_blur_score={filters.max_blur_score} 筛选: {before_count} -> {len(filtered)}")

        # 亮度筛选
        if filters.min_brightness_score is not None:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("brightness_score") is not None and img.get("brightness_score") >= filters.min_brightness_score
            ]
            logger.info(f"min_brightness_score={filters.min_brightness_score} 筛选: {before_count} -> {len(filtered)}")

        if filters.max_brightness_score is not None:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("brightness_score") is not None and img.get("brightness_score") <= filters.max_brightness_score
            ]
            logger.info(f"max_brightness_score={filters.max_brightness_score} 筛选: {before_count} -> {len(filtered)}")

        # 质量问题筛选
        if filters.has_quality_issues is not None:
            if filters.has_quality_issues:
                # 只显示有质量问题的图片
                filtered = [
                    img for img in filtered
                    if img.get("quality_issues") and len(img.get("quality_issues", [])) > 0
                ]
            else:
                # 只显示没有质量问题的图片
                filtered = [
                    img for img in filtered
                    if not img.get("quality_issues") or len(img.get("quality_issues", [])) == 0
                ]

        # 快捷筛选
        if filters.only_analyzed:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("quality_score") is not None
            ]
            logger.info(f"only_analyzed=True 筛选: {before_count} -> {len(filtered)}")

        if filters.only_unanalyzed:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("quality_score") is None
            ]
            logger.info(f"only_unanalyzed=True 筛选: {before_count} -> {len(filtered)}")

        # 收藏筛选
        if filters.favorite is not None:
            before_count = len(filtered)
            filtered = [
                img for img in filtered
                if img.get("favorite", False) == filters.favorite
            ]
            logger.info(f"favorite={filters.favorite} 筛选: {before_count} -> {len(filtered)}")

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

    async def toggle_favorite(self, image_id: str, favorite: bool) -> bool:
        """
        切换图片收藏状态

        Args:
            image_id: 图片ID
            favorite: 收藏状态

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
                        img["favorite"] = favorite
                        found = True
                        break

                if not found:
                    logger.warning(f"图片不存在: {image_id}")
                    return False

                # 保存
                await self.storage.save_image_metadata(data)
                logger.info(f"更新图片收藏状态成功: {image_id}, favorite={favorite}")
                return True

        except Exception as e:
            logger.error(f"更新图片收藏状态失败: {e}")
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

    async def check_missing_files(self) -> Dict[str, Any]:
        """
        检查哪些图片的文件已被删除（但元数据还在）

        Returns:
            包含失效图片列表的字典
        """
        try:
            data = await self.storage.load_image_metadata()
            images = data.get("images", [])

            missing_images = []
            valid_count = 0

            for img in images:
                filename = img.get("filename")
                if not filename:
                    continue

                file_path = self.image_dir / filename
                if not file_path.exists():
                    # 文件不存在，添加到失效列表
                    missing_images.append({
                        "id": img.get("id"),
                        "filename": filename,
                        "prompt": img.get("prompt", ""),
                        "quality_score": img.get("quality_score"),
                        "created_at": img.get("created_at"),
                        "file_size": img.get("file_size", 0),
                    })
                else:
                    valid_count += 1

            return {
                "total": len(images),
                "valid": valid_count,
                "missing": len(missing_images),
                "missing_images": missing_images
            }

        except Exception as e:
            logger.error(f"检查失效图片失败: {e}")
            return {
                "total": 0,
                "valid": 0,
                "missing": 0,
                "missing_images": []
            }

    async def scan_local_images(self) -> Dict[str, Any]:
        """
        扫描本地图片文件夹，为没有元数据的图片创建元数据

        注意：
        1. 只会为没有元数据的图片创建新记录，不会覆盖已有的元数据
        2. 优先从图片的 EXIF 数据中读取提示词
        3. 如果 EXIF 中没有提示词，则使用默认的"本地导入"

        Returns:
            扫描结果统计
        """
        try:
            from PIL import Image
            import uuid
            from .exif_manager import get_exif_manager

            # 获取 EXIF 管理器
            exif_manager = get_exif_manager()

            async with self.storage.acquire_lock("image_metadata", timeout=10):
                data = await self.storage.load_image_metadata()
                images = data.get("images", [])

                # 获取已有的文件名集合
                existing_filenames = {img.get("filename") for img in images}

                # 确保图片目录存在
                self.image_dir.mkdir(parents=True, exist_ok=True)

                # 扫描图片文件
                added_count = 0
                skipped_count = 0
                failed_count = 0
                restored_from_exif = 0

                # 支持的图片格式
                image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

                for file_path in self.image_dir.iterdir():
                    if not file_path.is_file():
                        continue

                    # 检查文件扩展名
                    if file_path.suffix.lower() not in image_extensions:
                        continue

                    # 如果已有元数据，跳过（不覆盖）
                    if file_path.name in existing_filenames:
                        skipped_count += 1
                        continue

                    try:
                        # ✨ 关键：尝试从图片的 EXIF 数据中读取元数据
                        exif_metadata = exif_manager.read_metadata_from_image(file_path)

                        # 读取图片信息
                        with Image.open(file_path) as img:
                            width, height = img.size
                            file_size = file_path.stat().st_size
                            created_at = int(file_path.stat().st_mtime * 1000)

                            # 计算宽高比
                            gcd_val = self._gcd(width, height)
                            aspect_w = width // gcd_val
                            aspect_h = height // gcd_val
                            aspect_ratio = f"{aspect_w}:{aspect_h}"

                            # 如果 EXIF 中有元数据，使用 EXIF 中的信息
                            if exif_metadata and "prompt" in exif_metadata:
                                prompt = exif_metadata.get("prompt", f"本地导入: {file_path.stem}")
                                model = exif_metadata.get("model", "grok-imagine-1.0")
                                exif_aspect_ratio = exif_metadata.get("aspect_ratio", aspect_ratio)
                                tags = []
                                restored_from_exif += 1
                                logger.info(f"从 EXIF 恢复元数据: {file_path.name}")
                            else:
                                # 如果 EXIF 中没有元数据，使用默认值
                                prompt = f"本地导入: {file_path.stem}"
                                model = "local-import"
                                exif_aspect_ratio = aspect_ratio
                                tags = ["本地导入"]

                            # 创建元数据
                            # 使用文件名（去掉扩展名）作为 id，确保 id 和 filename 匹配
                            metadata = ImageMetadata(
                                id=file_path.stem,
                                filename=file_path.name,
                                prompt=prompt,
                                model=model,
                                aspect_ratio=exif_aspect_ratio,
                                created_at=created_at,
                                file_size=file_size,
                                width=width,
                                height=height,
                                tags=tags,
                                nsfw=False,
                                metadata={}
                            )

                            # 添加到列表
                            images.append(metadata.model_dump())
                            added_count += 1
                            logger.info(f"扫描到新图片: {file_path.name}")

                    except Exception as e:
                        logger.error(f"处理图片失败 {file_path.name}: {e}")
                        failed_count += 1

                # 保存元数据
                if added_count > 0:
                    data["images"] = images
                    await self.storage.save_image_metadata(data)
                    logger.info(f"扫描完成: 新增 {added_count}, 跳过 {skipped_count}, 失败 {failed_count}, 从EXIF恢复 {restored_from_exif}")

                return {
                    "added": added_count,
                    "skipped": skipped_count,
                    "failed": failed_count,
                    "restored_from_exif": restored_from_exif,
                    "total": added_count + skipped_count + failed_count
                }

        except Exception as e:
            logger.error(f"扫描本地图片失败: {e}")
            return {
                "added": 0,
                "skipped": 0,
                "failed": 0,
                "restored_from_exif": 0,
                "total": 0,
                "error": str(e)
            }

    def _gcd(self, a: int, b: int) -> int:
        """计算最大公约数"""
        while b:
            a, b = b, a % b
        return a

    async def import_image(self, source_path: str, tags: Optional[List[str]] = None) -> Optional[str]:
        """
        从指定路径导入图片到图片文件夹

        Args:
            source_path: 源图片路径
            tags: 可选的标签列表

        Returns:
            导入成功返回图片ID，失败返回None
        """
        try:
            from PIL import Image
            import uuid
            import shutil
            import hashlib

            source = Path(source_path)
            if not source.exists() or not source.is_file():
                logger.error(f"源文件不存在: {source_path}")
                return None

            # 确保图片目录存在
            self.image_dir.mkdir(parents=True, exist_ok=True)

            # 读取文件内容并计算哈希
            file_bytes = source.read_bytes()
            content_hash = hashlib.sha256(file_bytes).hexdigest()

            # 检查是否已导入相同内容的图片
            existing_image = await self.find_image_by_hash(content_hash)
            if existing_image:
                logger.info(f"图片内容已存在，跳过导入: {source.name} (哈希: {content_hash[:16]}...)")
                return existing_image.id

            # 生成新文件名（保留原扩展名）
            image_id = str(uuid.uuid4())
            new_filename = f"{image_id}{source.suffix}"
            dest_path = self.image_dir / new_filename

            # 检查文件是否已存在（理论上不应该，但以防万一）
            if dest_path.exists():
                logger.warning(f"目标文件已存在，跳过导入: {new_filename}")
                return None

            # 复制文件
            shutil.copy2(source, dest_path)

            # 读取图片信息
            with Image.open(dest_path) as img:
                width, height = img.size
                file_size = dest_path.stat().st_size
                created_at = int(datetime.now().timestamp() * 1000)

                # 计算宽高比
                gcd_val = self._gcd(width, height)
                aspect_w = width // gcd_val
                aspect_h = height // gcd_val
                aspect_ratio = f"{aspect_w}:{aspect_h}"

                # 创建元数据（包含内容哈希）
                metadata = ImageMetadata(
                    id=image_id,
                    filename=new_filename,
                    prompt=f"导入: {source.stem}",
                    model="imported",
                    aspect_ratio=aspect_ratio,
                    created_at=created_at,
                    file_size=file_size,
                    width=width,
                    height=height,
                    tags=tags or ["导入"],
                    nsfw=False,
                    metadata={"source": str(source), "content_hash": content_hash}
                )

                # 添加元数据
                success = await self.add_image(metadata)
                if success:
                    logger.info(f"导入图片成功: {source.name} -> {new_filename}")
                    return image_id
                else:
                    # 如果添加元数据失败，删除已复制的文件
                    dest_path.unlink()
                    logger.error(f"添加元数据失败，已删除文件: {new_filename}")
                    return None

        except Exception as e:
            logger.error(f"导入图片失败: {e}")
            return None


# 全局单例
_service_instance: Optional[ImageMetadataService] = None


def get_image_metadata_service() -> ImageMetadataService:
    """获取图片元数据服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = ImageMetadataService()
    return _service_instance
