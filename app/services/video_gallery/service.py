"""
视频元数据管理服务
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from app.core.storage import get_storage
from app.core.logger import logger
from .models import VideoMetadata, VideoListResponse, VideoFilter, VideoStats


class VideoMetadataService:
    """视频元数据管理服务"""

    def __init__(self):
        self.storage = get_storage()
        self.video_dir = Path(__file__).parent.parent.parent.parent / "data" / "tmp" / "video"

    async def add_video(self, metadata: VideoMetadata) -> bool:
        """
        添加视频元数据

        Args:
            metadata: 视频元数据

        Returns:
            是否添加成功
        """
        try:
            async with self.storage.acquire_lock("video_metadata", timeout=10):
                data = await self.storage.load_video_metadata()

                existing_ids = {v["id"] for v in data.get("videos", [])}
                if metadata.id in existing_ids:
                    logger.warning(f"视频元数据已存在: {metadata.id}")
                    return False

                existing_filenames = {v.get("filename") for v in data.get("videos", [])}
                if metadata.filename in existing_filenames:
                    logger.warning(f"视频文件名已存在: {metadata.filename}")
                    return False

                data.setdefault("videos", []).append(metadata.model_dump())
                await self.storage.save_video_metadata(data)
                logger.info(f"添加视频元数据成功: {metadata.id}")

            return True

        except Exception as e:
            logger.error(f"添加视频元数据失败: {e}")
            return False

    async def get_video(self, video_id: str) -> Optional[VideoMetadata]:
        """
        获取视频详情

        Args:
            video_id: 视频 ID

        Returns:
            视频元数据，不存在返回 None
        """
        try:
            data = await self.storage.load_video_metadata()

            for v in data.get("videos", []):
                if v.get("id") == video_id:
                    return VideoMetadata(**v)

            return None

        except Exception as e:
            logger.error(f"获取视频详情失败: {e}")
            return None

    async def list_videos(
        self,
        filters: Optional[VideoFilter] = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> VideoListResponse:
        """
        列出视频（支持筛选、分页、排序）

        Args:
            filters: 筛选条件
            page: 页码（从 1 开始）
            page_size: 每页数量
            sort_by: 排序字段
            sort_order: 排序顺序（asc/desc）

        Returns:
            视频列表响应
        """
        try:
            data = await self.storage.load_video_metadata()
            videos = data.get("videos", [])

            if filters:
                videos = self._apply_filters(videos, filters)

            reverse = sort_order.lower() == "desc"
            videos.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)

            total = len(videos)
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            start = (page - 1) * page_size
            end = start + page_size
            page_videos = videos[start:end]

            for v in page_videos:
                v["file_path"] = str(self.video_dir / v["filename"])
                v["relative_path"] = f"data/tmp/video/{v['filename']}"

            video_models = [VideoMetadata(**v) for v in page_videos]

            return VideoListResponse(
                videos=video_models,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )

        except Exception as e:
            logger.error(f"列出视频失败: {e}")
            return VideoListResponse(
                videos=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )

    def _apply_filters(self, videos: List[Dict], filters: VideoFilter) -> List[Dict]:
        """应用筛选条件"""
        filtered = videos

        if filters.search:
            search_lower = filters.search.lower()
            filtered = [
                v for v in filtered
                if search_lower in v.get("prompt", "").lower()
            ]

        if filters.model:
            filtered = [v for v in filtered if v.get("model") == filters.model]

        if filters.aspect_ratio:
            filtered = [v for v in filtered if v.get("aspect_ratio") == filters.aspect_ratio]

        if filters.video_length is not None:
            filtered = [v for v in filtered if v.get("video_length") == filters.video_length]

        if filters.resolution:
            filtered = [v for v in filtered if v.get("resolution") == filters.resolution]

        if filters.preset:
            filtered = [v for v in filtered if v.get("preset") == filters.preset]

        if filters.tags:
            filtered = [
                v for v in filtered
                if any(tag in v.get("tags", []) for tag in filters.tags)
            ]

        if filters.start_date:
            filtered = [v for v in filtered if v.get("created_at", 0) >= filters.start_date]

        if filters.end_date:
            filtered = [v for v in filtered if v.get("created_at", 0) <= filters.end_date]

        if filters.favorite is not None:
            filtered = [v for v in filtered if v.get("favorite", False) == filters.favorite]

        return filtered

    async def delete_videos(self, video_ids: List[str]) -> Dict[str, Any]:
        """
        批量删除视频（文件 + 元数据）

        Args:
            video_ids: 视频 ID 列表

        Returns:
            删除结果统计
        """
        deleted_count = 0
        failed_count = 0

        try:
            async with self.storage.acquire_lock("video_metadata", timeout=10):
                data = await self.storage.load_video_metadata()
                videos = data.get("videos", [])

                to_delete = []
                remaining = []

                for v in videos:
                    if v.get("id") in video_ids:
                        to_delete.append(v)
                    else:
                        remaining.append(v)

                for v in to_delete:
                    try:
                        file_path = self.video_dir / v.get("filename", "")
                        if file_path.exists():
                            file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除视频文件失败 {v.get('id')}: {e}")
                        failed_count += 1

                data["videos"] = remaining
                await self.storage.save_video_metadata(data)

                logger.info(f"批量删除视频: 成功 {deleted_count}, 失败 {failed_count}")

        except Exception as e:
            logger.error(f"批量删除视频失败: {e}")

        return {
            "deleted": deleted_count,
            "failed": failed_count,
            "total": len(video_ids),
        }

    async def update_tags(self, video_id: str, tags: List[str]) -> bool:
        """更新视频标签"""
        try:
            async with self.storage.acquire_lock("video_metadata", timeout=10):
                data = await self.storage.load_video_metadata()
                videos = data.get("videos", [])

                found = False
                for v in videos:
                    if v.get("id") == video_id:
                        v["tags"] = tags
                        found = True
                        break

                if not found:
                    logger.warning(f"视频不存在: {video_id}")
                    return False

                await self.storage.save_video_metadata(data)
                logger.info(f"更新视频标签成功: {video_id}")
                return True

        except Exception as e:
            logger.error(f"更新视频标签失败: {e}")
            return False

    async def toggle_favorite(self, video_id: str, favorite: bool) -> bool:
        """切换视频收藏状态"""
        try:
            async with self.storage.acquire_lock("video_metadata", timeout=10):
                data = await self.storage.load_video_metadata()
                videos = data.get("videos", [])

                found = False
                for v in videos:
                    if v.get("id") == video_id:
                        v["favorite"] = favorite
                        found = True
                        break

                if not found:
                    logger.warning(f"视频不存在: {video_id}")
                    return False

                await self.storage.save_video_metadata(data)
                logger.info(f"更新视频收藏状态成功: {video_id}, favorite={favorite}")
                return True

        except Exception as e:
            logger.error(f"更新视频收藏状态失败: {e}")
            return False

    async def get_all_tags(self) -> List[Dict[str, Any]]:
        """获取所有标签及其使用次数"""
        try:
            data = await self.storage.load_video_metadata()
            videos = data.get("videos", [])

            tag_counts: Dict[str, int] = {}
            for v in videos:
                for tag in v.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            tags = [
                {"name": tag, "count": count}
                for tag, count in tag_counts.items()
            ]
            tags.sort(key=lambda x: x["count"], reverse=True)

            return tags

        except Exception as e:
            logger.error(f"获取标签列表失败: {e}")
            return []

    async def get_stats(self) -> VideoStats:
        """获取统计信息"""
        try:
            data = await self.storage.load_video_metadata()
            videos = data.get("videos", [])

            total_count = len(videos)
            total_size = sum(v.get("file_size", 0) or 0 for v in videos)

            now = datetime.now()
            month_start = datetime(now.year, now.month, 1)
            month_start_ts = int(month_start.timestamp() * 1000)
            month_count = sum(
                1 for v in videos
                if v.get("created_at", 0) >= month_start_ts
            )

            tag_counts: Dict[str, int] = {}
            for v in videos:
                for tag in v.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            top_tags = [
                {"name": tag, "count": count}
                for tag, count in sorted(
                    tag_counts.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ]

            resolutions: Dict[str, int] = {}
            for v in videos:
                res = v.get("resolution", "unknown")
                resolutions[res] = resolutions.get(res, 0) + 1

            presets: Dict[str, int] = {}
            for v in videos:
                preset = v.get("preset", "unknown")
                presets[preset] = presets.get(preset, 0) + 1

            aspect_ratios: Dict[str, int] = {}
            for v in videos:
                ratio = v.get("aspect_ratio", "unknown")
                aspect_ratios[ratio] = aspect_ratios.get(ratio, 0) + 1

            return VideoStats(
                total_count=total_count,
                total_size=total_size,
                month_count=month_count,
                top_tags=top_tags,
                resolutions=resolutions,
                presets=presets,
                aspect_ratios=aspect_ratios,
            )

        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return VideoStats()

    async def cleanup_orphaned_metadata(self) -> int:
        """清理孤立的元数据（文件不存在但元数据存在）"""
        try:
            async with self.storage.acquire_lock("video_metadata", timeout=10):
                data = await self.storage.load_video_metadata()
                videos = data.get("videos", [])

                valid_videos = []
                removed_count = 0

                for v in videos:
                    file_path = self.video_dir / v.get("filename", "")
                    if file_path.exists():
                        valid_videos.append(v)
                    else:
                        removed_count += 1
                        logger.info(f"清理孤立视频元数据: {v.get('id')}")

                if removed_count > 0:
                    data["videos"] = valid_videos
                    await self.storage.save_video_metadata(data)
                    logger.info(f"清理孤立视频元数据完成: {removed_count} 条")

                return removed_count

        except Exception as e:
            logger.error(f"清理孤立视频元数据失败: {e}")
            return 0

    async def check_missing_files(self) -> Dict[str, Any]:
        """检查哪些视频的文件已被删除（但元数据还在）"""
        try:
            data = await self.storage.load_video_metadata()
            videos = data.get("videos", [])

            missing_videos = []
            valid_count = 0

            for v in videos:
                filename = v.get("filename")
                if not filename:
                    continue

                file_path = self.video_dir / filename
                if not file_path.exists():
                    missing_videos.append({
                        "id": v.get("id"),
                        "filename": filename,
                        "prompt": v.get("prompt", ""),
                        "created_at": v.get("created_at"),
                        "file_size": v.get("file_size", 0),
                    })
                else:
                    valid_count += 1

            return {
                "total": len(videos),
                "valid": valid_count,
                "missing": len(missing_videos),
                "missing_videos": missing_videos,
            }

        except Exception as e:
            logger.error(f"检查失效视频失败: {e}")
            return {
                "total": 0,
                "valid": 0,
                "missing": 0,
                "missing_videos": [],
            }

    async def scan_local_videos(self) -> Dict[str, Any]:
        """
        扫描本地视频文件夹，为没有元数据的视频创建元数据

        Returns:
            扫描结果统计
        """
        try:
            import uuid

            async with self.storage.acquire_lock("video_metadata", timeout=10):
                data = await self.storage.load_video_metadata()
                videos = data.get("videos", [])

                existing_filenames = {v.get("filename") for v in videos}

                self.video_dir.mkdir(parents=True, exist_ok=True)

                added_count = 0
                skipped_count = 0
                failed_count = 0

                video_extensions = {".mp4", ".webm"}

                for file_path in self.video_dir.iterdir():
                    if not file_path.is_file():
                        continue

                    if file_path.suffix.lower() not in video_extensions:
                        continue

                    if file_path.name in existing_filenames:
                        skipped_count += 1
                        continue

                    try:
                        file_size = file_path.stat().st_size
                        created_at = int(file_path.stat().st_mtime * 1000)

                        metadata = VideoMetadata(
                            id=file_path.stem,
                            filename=file_path.name,
                            prompt=f"本地导入: {file_path.stem}",
                            model="local-import",
                            created_at=created_at,
                            file_size=file_size,
                            tags=["本地导入"],
                        )

                        videos.append(metadata.model_dump())
                        added_count += 1
                        logger.info(f"扫描到新视频: {file_path.name}")

                    except Exception as e:
                        logger.error(f"处理视频失败 {file_path.name}: {e}")
                        failed_count += 1

                if added_count > 0:
                    data["videos"] = videos
                    await self.storage.save_video_metadata(data)
                    logger.info(
                        f"视频扫描完成: 新增 {added_count}, 跳过 {skipped_count}, 失败 {failed_count}"
                    )

                return {
                    "added": added_count,
                    "skipped": skipped_count,
                    "failed": failed_count,
                    "total": added_count + skipped_count + failed_count,
                }

        except Exception as e:
            logger.error(f"扫描本地视频失败: {e}")
            return {
                "added": 0,
                "skipped": 0,
                "failed": 0,
                "total": 0,
                "error": str(e),
            }

    async def get_tracked_filenames(self) -> set[str]:
        """获取所有被追踪的视频文件名（用于清理守卫）"""
        try:
            data = await self.storage.load_video_metadata()
            return {v.get("filename", "") for v in data.get("videos", []) if v.get("filename")}
        except Exception:
            return set()


# 全局单例
_service_instance: Optional[VideoMetadataService] = None


def get_video_metadata_service() -> VideoMetadataService:
    """获取视频元数据服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = VideoMetadataService()
    return _service_instance
