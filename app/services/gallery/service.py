"""
图片元数据管理服务
"""

import os
import sys
import asyncio
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.core.storage import get_storage
from app.core.logger import logger
from .models import ImageMetadata, ImageListResponse, ImageFilter, ImageStats
from .backup import get_backup_service

# 添加项目根目录到路径，以便导入 advanced_image_analyzer
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from advanced_image_analyzer import AdvancedImageQualityAnalyzer
    ADVANCED_ANALYZER_AVAILABLE = True
except ImportError:
    ADVANCED_ANALYZER_AVAILABLE = False
    logger.warning("高级图片分析器不可用，将使用基础分析器")

try:
    from simple_object_detector import SimpleObjectDetector
    SIMPLE_DETECTOR_AVAILABLE = True
except ImportError:
    SIMPLE_DETECTOR_AVAILABLE = False
    logger.warning("简单物体检测器不可用")


class ImageMetadataService:
    """图片元数据管理服务"""

    def __init__(self):
        self.storage = get_storage()
        self.image_dir = Path(__file__).parent.parent.parent.parent / "data" / "tmp" / "image"

        # 初始化高级图片分析器（懒加载）
        self._analyzer = None

        # 初始化简单物体检测器（懒加载）
        self._object_detector = None

        # 分析停止标志
        self._stop_analysis = False

    def _get_analyzer(self):
        """获取分析器实例（懒加载）"""
        if self._analyzer is None and ADVANCED_ANALYZER_AVAILABLE:
            try:
                self._analyzer = AdvancedImageQualityAnalyzer(use_clip=True)
                logger.info("[OK] 高级图片分析器初始化成功（CLIP + OpenCV）")
            except Exception as e:
                logger.warning(f"CLIP 模型加载失败，使用轻量级模式: {e}")
                try:
                    self._analyzer = AdvancedImageQualityAnalyzer(use_clip=False)
                    logger.info("[OK] 轻量级图片分析器初始化成功（纯 OpenCV）")
                except Exception as e2:
                    logger.error(f"图片分析器初始化失败: {e2}")
                    self._analyzer = None
        return self._analyzer

    def _get_object_detector(self):
        """获取简单物体检测器实例（懒加载）"""
        if self._object_detector is None and SIMPLE_DETECTOR_AVAILABLE:
            try:
                self._object_detector = SimpleObjectDetector()
                logger.info("[OK] 简单物体检测器初始化成功")
            except Exception as e:
                logger.error(f"物体检测器初始化失败: {e}")
                self._object_detector = None
        return self._object_detector

    async def add_image(self, metadata: ImageMetadata, auto_analyze: bool = True) -> bool:
        """
        添加图片元数据

        Args:
            metadata: 图片元数据
            auto_analyze: 是否自动分析图片质量（默认True）

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

            # 自动分析图片质量（在锁外执行，避免阻塞）
            if auto_analyze:
                try:
                    logger.info(f"开始自动分析图片质量: {metadata.id}")
                    quality_result = await self.analyze_image_quality(metadata.id)
                    if quality_result:
                        # 更新质量分数到元数据
                        await self.update_image(metadata.id, {
                            "quality_score": quality_result.get("quality_score"),
                            "blur_score": quality_result.get("blur_score"),
                            "brightness_score": quality_result.get("brightness_score"),
                            "contrast_score": quality_result.get("contrast_score"),
                            "quality_issues": quality_result.get("quality_issues", []),
                        })
                        logger.info(f"自动分析完成，质量分数: {quality_result.get('quality_score')}")
                    else:
                        logger.warning(f"自动分析失败: {metadata.id}")
                except Exception as e:
                    logger.error(f"自动分析图片质量失败: {e}")
                    # 不影响添加图片的成功状态

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

    async def analyze_image_quality(self, image_id: str) -> Optional[Dict[str, Any]]:
        """
        分析单张图片的质量（增强版）

        使用 CLIP + OpenCV 混合方案，可以：
        - 检测技术质量（清晰度、亮度、对比度、噪点等）
        - 识别内容合理性（构图、光影、色彩等）
        - 检测 AI 生成缺陷（手部、面部、文字等）

        Args:
            image_id: 图片ID

        Returns:
            质量分析结果
        """
        try:
            # 获取图片元数据
            metadata = await self.get_image(image_id)
            if not metadata:
                logger.error(f"图片不存在: {image_id}")
                return None

            # 检查文件是否存在
            file_path = self.image_dir / metadata.filename
            if not file_path.exists():
                logger.error(f"图片文件不存在: {file_path}")
                return None

            # 获取分析器
            analyzer = self._get_analyzer()

            if analyzer:
                # 使用高级分析器
                result = analyzer.comprehensive_analysis(str(file_path))

                # 格式化结果
                return {
                    "quality_score": result["final_score"],
                    "grade": result["grade"],
                    "blur_score": result["technical"].get("sharpness", 0),
                    "brightness_score": result["technical"].get("brightness", 0),
                    "contrast_score": result["technical"].get("contrast", 0),
                    "quality_issues": result["issues"],
                    "technical_scores": result["technical"],
                    "content_scores": result.get("content", {}),
                    "defect_scores": result.get("defects", {}),
                    "using_clip": result.get("using_clip", False)
                }
            else:
                # 降级到基础 OpenCV 分析
                import cv2
                import numpy as np

                img = cv2.imread(str(file_path))
                if img is None:
                    logger.error(f"无法读取图片: {file_path}")
                    return None

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                # 基础分析
                laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
                if laplacian_var < 50:
                    blur_score = laplacian_var / 50 * 40
                elif laplacian_var < 200:
                    blur_score = 40 + (laplacian_var - 50) / 150 * 40
                else:
                    blur_score = 80 + min(20, (laplacian_var - 200) / 100 * 20)
                blur_score = max(0, min(100, blur_score))

                brightness = np.mean(gray)
                brightness_score = brightness / 255 * 100

                contrast = gray.std()
                if contrast < 20:
                    contrast_score = contrast / 20 * 50
                elif contrast < 50:
                    contrast_score = 50 + (contrast - 20) / 30 * 30
                else:
                    contrast_score = 80 + min(20, (contrast - 50) / 30 * 20)
                contrast_score = max(0, min(100, contrast_score))

                quality_issues = []
                if blur_score < 40:
                    quality_issues.append("图片模糊")
                if brightness_score < 15 or brightness_score > 85:
                    quality_issues.append("亮度异常")
                if contrast_score < 30:
                    quality_issues.append("对比度过低")

                quality_score = (
                    blur_score * 0.5 +
                    contrast_score * 0.3 +
                    (100 - abs(brightness_score - 50) * 1.5) * 0.2
                )
                quality_score = max(0, min(100, quality_score))

                return {
                    "quality_score": float(round(quality_score, 2)),
                    "blur_score": float(round(blur_score, 2)),
                    "brightness_score": float(round(brightness_score, 2)),
                    "contrast_score": float(round(contrast_score, 2)),
                    "quality_issues": quality_issues,
                    "using_clip": False
                }

        except Exception as e:
            logger.error(f"分析图片质量失败 {image_id}: {e}")
            return None

    async def batch_analyze_quality(
        self,
        image_ids: Optional[List[str]] = None,
        update_metadata: bool = True,
        batch_size: int = 50,
        skip_analyzed: bool = False,
        max_workers: int = 8,
        fast_mode: bool = True
    ) -> Dict[str, Any]:
        """
        批量分析图片质量

        Args:
            image_ids: 图片ID列表，为None时分析所有图片
            update_metadata: 是否更新元数据
            batch_size: 批处理大小
            skip_analyzed: 是否跳过已分析的图片
            max_workers: 并发线程数（1-16）
            fast_mode: 是否使用快速模式（仅检测模糊，默认True）

        Returns:
            分析结果统计
        """
        try:
            # 重置停止标志
            self._stop_analysis = False

            # 获取要分析的图片列表
            data = await self.storage.load_image_metadata()
            all_images = data.get("images", [])

            # 按照创建时间倒序排序（最新的图片优先分析）
            all_images.sort(key=lambda x: x.get("created_at", 0), reverse=True)

            if image_ids is None:
                # 分析所有图片
                image_ids = [img["id"] for img in all_images]
            else:
                # 保持指定图片的顺序，但也按创建时间排序
                id_to_img = {img["id"]: img for img in all_images}
                sorted_specified = sorted(
                    [id_to_img[img_id] for img_id in image_ids if img_id in id_to_img],
                    key=lambda x: x.get("created_at", 0),
                    reverse=True
                )
                image_ids = [img["id"] for img in sorted_specified]

            original_total = len(image_ids)

            # 如果启用跳过模式，过滤掉已分析的图片
            if skip_analyzed:
                all_images_dict = {img["id"]: img for img in all_images}
                unanalyzed_ids = [
                    img_id for img_id in image_ids
                    if img_id in all_images_dict and
                       all_images_dict[img_id].get("quality_score") is None
                ]
                skipped_count = len(image_ids) - len(unanalyzed_ids)
                image_ids = unanalyzed_ids
                logger.info(f"增量分析模式：需分析 {len(image_ids)} 张图片（跳过已分析 {skipped_count} 张）")
            else:
                logger.info(f"全量分析模式：需分析 {len(image_ids)} 张图片")

            total = len(image_ids)
            analyzed = 0
            failed = 0
            low_quality_count = 0

            if total == 0:
                logger.info("没有需要分析的图片")
                return {
                    "total": 0,
                    "analyzed": 0,
                    "failed": 0,
                    "low_quality_count": 0,
                    "skipped": original_total if skip_analyzed else 0,
                    "stopped": False
                }

            mode_name = "快速模式（检测物体）" if fast_mode else "完整模式（综合分析）"
            logger.info(f"开始批量分析图片质量: 共 {total} 张，并发数 {max_workers}，模式: {mode_name}")

            # 分批处理
            for i in range(0, total, batch_size):
                # 检查停止标志
                if self._stop_analysis:
                    logger.info(f"分析已停止: 已完成 {analyzed}/{total} 张")
                    return {
                        "total": total,
                        "analyzed": analyzed,
                        "failed": failed,
                        "low_quality_count": low_quality_count,
                        "skipped": original_total - total if skip_analyzed else 0,
                        "stopped": True
                    }

                batch_ids = image_ids[i:i + batch_size]

                # 使用线程池并行处理
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有任务
                    future_to_id = {
                        executor.submit(self._analyze_image_sync, img_id, fast_mode): img_id
                        for img_id in batch_ids
                    }

                    # 收集结果
                    for future in as_completed(future_to_id):
                        # 再次检查停止标志
                        if self._stop_analysis:
                            # 取消剩余任务
                            for f in future_to_id:
                                f.cancel()
                            break

                        img_id = future_to_id[future]
                        try:
                            result = future.result()
                            if result:
                                analyzed += 1
                                if result["quality_score"] < 60:
                                    low_quality_count += 1

                                # 更新元数据
                                if update_metadata:
                                    await self._update_quality_metadata(img_id, result)
                            else:
                                failed += 1
                        except Exception as e:
                            logger.error(f"分析图片失败 {img_id}: {e}")
                            failed += 1

                # 记录进度
                progress = (i + len(batch_ids)) / total * 100
                logger.info(f"分析进度: {progress:.1f}% ({i + len(batch_ids)}/{total})")

            logger.info(f"批量分析完成: 成功 {analyzed}, 失败 {failed}, 低质量 {low_quality_count}")

            return {
                "total": total,
                "analyzed": analyzed,
                "failed": failed,
                "low_quality_count": low_quality_count,
                "low_quality_threshold": 60,
                "skipped": original_total - total if skip_analyzed else 0,
                "stopped": False
            }

        except Exception as e:
            logger.error(f"批量分析图片质量失败: {e}")
            return {
                "total": 0,
                "analyzed": 0,
                "failed": 0,
                "low_quality_count": 0,
                "error": str(e),
                "stopped": False
            }

    def stop_analysis(self):
        """停止正在进行的分析"""
        self._stop_analysis = True
        logger.info("收到停止分析请求")

    async def _update_quality_metadata(self, image_id: str, quality_result: Dict[str, Any]) -> bool:
        """
        更新图片的质量元数据

        Args:
            image_id: 图片ID
            quality_result: 质量分析结果

        Returns:
            是否更新成功
        """
        try:
            import numpy as np

            # 转换 NumPy 类型为 Python 原生类型
            def convert_to_native(obj):
                """递归转换 NumPy 类型为 Python 原生类型"""
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_to_native(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_native(item) for item in obj]
                else:
                    return obj

            # 转换质量结果中的所有值
            quality_result = convert_to_native(quality_result)

            async with self.storage.acquire_lock("image_metadata", timeout=10):
                data = await self.storage.load_image_metadata()
                images = data.get("images", [])

                # 查找并更新
                found = False
                for img in images:
                    if img.get("id") == image_id:
                        img["quality_score"] = quality_result["quality_score"]
                        img["blur_score"] = quality_result["blur_score"]
                        img["brightness_score"] = quality_result["brightness_score"]
                        img["quality_issues"] = quality_result["quality_issues"]
                        found = True
                        break

                if not found:
                    return False

                # 保存
                await self.storage.save_image_metadata(data)
                return True

        except Exception as e:
            logger.error(f"更新质量元数据失败 {image_id}: {e}")
            return False

    def _analyze_image_sync(self, image_id: str, fast_mode: bool = True) -> Optional[Dict[str, Any]]:
        """
        线程池执行的同步包装器
        为每个线程创建独立的事件循环来执行异步操作

        Args:
            image_id: 图片ID
            fast_mode: 是否使用快速模式（仅检测模糊）
        """
        try:
            # 为线程创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # 获取图片元数据
                metadata = loop.run_until_complete(self.get_image(image_id))
            finally:
                loop.close()

            if not metadata:
                return None

            # 检查文件存在性
            file_path = self.image_dir / metadata.filename
            if not file_path.exists():
                logger.warning(f"图片文件不存在: {file_path}")
                return None

            # 执行分析（CPU 密集型操作）
            if fast_mode:
                # 快速模式：仅检测物体
                detector = self._get_object_detector()
                if detector:
                    result = detector.detect(str(file_path))
                    if result.get("success"):
                        return {
                            "quality_score": result["quality_score"],
                            "blur_score": result["blur_score"],
                            "brightness_score": result["brightness_score"],
                            "quality_issues": result["quality_issues"]
                        }
                return None
            else:
                # 完整模式：综合分析
                analyzer = self._get_analyzer()
                if analyzer:
                    result = analyzer.comprehensive_analysis(str(file_path))
                    return {
                        "quality_score": result["final_score"],
                        "blur_score": result["technical"].get("sharpness", 0),
                        "brightness_score": result["technical"].get("brightness", 0),
                        "quality_issues": result["issues"]
                    }
                return None
        except Exception as e:
            logger.error(f"同步分析失败 {image_id}: {e}")
            return None

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
