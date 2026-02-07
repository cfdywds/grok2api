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
                if img.get("quality_score") is not None and img.get("quality_score") <= filters.max_quality_score
            ]
            logger.info(f"max_quality_score={filters.max_quality_score} 筛选: {before_count} -> {len(filtered)}")

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

    async def scan_local_images(self) -> Dict[str, Any]:
        """
        扫描本地图片文件夹，为没有元数据的图片创建元数据

        Returns:
            扫描结果统计
        """
        try:
            from PIL import Image
            import uuid

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

                # 支持的图片格式
                image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

                for file_path in self.image_dir.iterdir():
                    if not file_path.is_file():
                        continue

                    # 检查文件扩展名
                    if file_path.suffix.lower() not in image_extensions:
                        continue

                    # 如果已有元数据，跳过
                    if file_path.name in existing_filenames:
                        skipped_count += 1
                        continue

                    try:
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

                            # 创建元数据
                            metadata = ImageMetadata(
                                id=str(uuid.uuid4()),
                                filename=file_path.name,
                                prompt=f"本地导入: {file_path.stem}",
                                model="local-import",
                                aspect_ratio=aspect_ratio,
                                created_at=created_at,
                                file_size=file_size,
                                width=width,
                                height=height,
                                tags=["本地导入"],
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
                    logger.info(f"扫描完成: 新增 {added_count}, 跳过 {skipped_count}, 失败 {failed_count}")

                return {
                    "added": added_count,
                    "skipped": skipped_count,
                    "failed": failed_count,
                    "total": added_count + skipped_count + failed_count
                }

        except Exception as e:
            logger.error(f"扫描本地图片失败: {e}")
            return {
                "added": 0,
                "skipped": 0,
                "failed": 0,
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
        分析单张图片的质量

        Args:
            image_id: 图片ID

        Returns:
            质量分析结果，包含 quality_score, blur_score, brightness_score, quality_issues
        """
        try:
            import cv2
            import numpy as np

            # 获取图片元数据
            metadata = await self.get_image(image_id)
            if not metadata:
                logger.error(f"图片不存在: {image_id}")
                return None

            # 读取图片文件
            file_path = self.image_dir / metadata.filename
            if not file_path.exists():
                logger.error(f"图片文件不存在: {file_path}")
                return None

            # 使用OpenCV读取图片
            img = cv2.imread(str(file_path))
            if img is None:
                logger.error(f"无法读取图片: {file_path}")
                return None

            # 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 1. 模糊度检测（拉普拉斯方差）
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            # 归一化到0-100，通常清晰图片的方差 > 100
            blur_score = min(100, laplacian_var / 10)

            # 2. 亮度检测
            brightness = np.mean(gray)
            # 归一化到0-100，50为正常
            brightness_score = brightness / 255 * 100

            # 3. 对比度检测
            contrast = gray.std()
            # 归一化，通常对比度 > 30 为正常
            contrast_score = min(100, contrast / 0.5)

            # 4. 综合质量评分
            quality_issues = []

            # 极度模糊检测（阈值：20，针对马赛克、完全看不清的情况）
            if blur_score < 20:
                quality_issues.append("极度模糊")
            # 严重模糊检测（阈值：35）
            elif blur_score < 35:
                quality_issues.append("严重模糊")

            # 极度过暗检测（阈值：10，几乎全黑）
            if brightness_score < 10:
                quality_issues.append("极度过暗")
            # 极度过亮检测（阈值：90，几乎全白）
            elif brightness_score > 90:
                quality_issues.append("极度过亮")

            # 极低对比度检测（阈值：25，图片发灰严重）
            if contrast_score < 25:
                quality_issues.append("极低对比度")

            # 计算综合评分（加权平均，模糊度权重大幅提高）
            quality_score = (
                blur_score * 0.7 +  # 模糊度权重大幅提高，主要筛选看不清的图片
                contrast_score * 0.2 +  # 对比度权重降低
                (100 - abs(brightness_score - 50) * 2) * 0.1  # 亮度权重降低
            )
            quality_score = max(0, min(100, quality_score))

            result = {
                "quality_score": float(round(quality_score, 2)),
                "blur_score": float(round(blur_score, 2)),
                "brightness_score": float(round(brightness_score, 2)),
                "contrast_score": float(round(contrast_score, 2)),
                "quality_issues": quality_issues
            }

            logger.info(f"图片质量分析完成: {image_id}, 评分: {quality_score:.2f}")
            return result

        except Exception as e:
            logger.error(f"分析图片质量失败 {image_id}: {e}")
            return None

    async def batch_analyze_quality(
        self,
        image_ids: Optional[List[str]] = None,
        update_metadata: bool = True,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        批量分析图片质量

        Args:
            image_ids: 图片ID列表，为None时分析所有图片
            update_metadata: 是否更新元数据
            batch_size: 批处理大小

        Returns:
            分析结果统计
        """
        try:
            # 获取要分析的图片列表
            if image_ids is None:
                data = await self.storage.load_image_metadata()
                all_images = data.get("images", [])
                image_ids = [img["id"] for img in all_images]

            total = len(image_ids)
            analyzed = 0
            failed = 0
            low_quality_count = 0

            logger.info(f"开始批量分析图片质量: 共 {total} 张")

            # 分批处理
            for i in range(0, total, batch_size):
                batch_ids = image_ids[i:i + batch_size]

                for image_id in batch_ids:
                    result = await self.analyze_image_quality(image_id)

                    if result:
                        analyzed += 1

                        # 统计低质量图片（评分 < 60）
                        if result["quality_score"] < 60:
                            low_quality_count += 1

                        # 更新元数据
                        if update_metadata:
                            await self._update_quality_metadata(image_id, result)
                    else:
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
                "low_quality_threshold": 60
            }

        except Exception as e:
            logger.error(f"批量分析图片质量失败: {e}")
            return {
                "total": 0,
                "analyzed": 0,
                "failed": 0,
                "low_quality_count": 0,
                "error": str(e)
            }

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

            source = Path(source_path)
            if not source.exists() or not source.is_file():
                logger.error(f"源文件不存在: {source_path}")
                return None

            # 确保图片目录存在
            self.image_dir.mkdir(parents=True, exist_ok=True)

            # 生成新文件名（保留原扩展名）
            image_id = str(uuid.uuid4())
            new_filename = f"{image_id}{source.suffix}"
            dest_path = self.image_dir / new_filename

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

                # 创建元数据
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
                    metadata={"source": str(source)}
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
