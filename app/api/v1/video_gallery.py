"""
视频管理 API 路由
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.logger import logger
from app.services.video_gallery import (
    VideoFilter,
    VideoListResponse,
    VideoStats,
)
from app.services.video_gallery.service import get_video_metadata_service


router = APIRouter(prefix="/api/v1/admin/video-gallery", tags=["Video Gallery"])


class DeleteVideosRequest(BaseModel):
    """批量删除视频请求"""
    video_ids: List[str]


class UpdateTagsRequest(BaseModel):
    """更新标签请求"""
    tags: List[str]


class ToggleFavoriteRequest(BaseModel):
    """切换收藏请求"""
    favorite: bool


@router.post("/scan")
async def scan_local_videos():
    """扫描本地视频文件夹，为没有元数据的视频创建元数据"""
    try:
        service = get_video_metadata_service()
        result = await service.scan_local_videos()

        return {
            "success": True,
            "message": f"扫描完成: 新增 {result['added']}, 跳过 {result['skipped']}, 失败 {result['failed']}",
            "data": result,
        }

    except Exception as e:
        logger.error(f"扫描本地视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"扫描本地视频失败: {str(e)}")


@router.get("/videos", response_model=VideoListResponse)
async def list_videos(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    model: Optional[str] = Query(None, description="模型筛选"),
    aspect_ratio: Optional[str] = Query(None, description="宽高比筛选"),
    video_length: Optional[int] = Query(None, description="视频时长筛选（6/10/15）"),
    resolution: Optional[str] = Query(None, description="分辨率筛选"),
    preset: Optional[str] = Query(None, description="预设风格筛选"),
    tags: Optional[str] = Query(None, description="标签筛选（逗号分隔）"),
    start_date: Optional[int] = Query(None, description="开始日期（时间戳）"),
    end_date: Optional[int] = Query(None, description="结束日期（时间戳）"),
    favorite: Optional[bool] = Query(None, description="是否筛选收藏的视频"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序顺序（asc/desc）"),
):
    """获取视频列表（支持分页、筛选、排序）"""
    try:
        service = get_video_metadata_service()

        filters = VideoFilter(
            search=search,
            model=model,
            aspect_ratio=aspect_ratio,
            video_length=video_length,
            resolution=resolution,
            preset=preset,
            tags=tags.split(",") if tags else None,
            start_date=start_date,
            end_date=end_date,
            favorite=favorite,
        )

        result = await service.list_videos(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return result

    except Exception as e:
        logger.error(f"获取视频列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频列表失败: {str(e)}")


@router.get("/videos/{video_id}")
async def get_video(video_id: str):
    """获取视频详情"""
    try:
        service = get_video_metadata_service()
        video = await service.get_video(video_id)

        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")

        return video

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取视频详情失败: {str(e)}")


@router.get("/videos/{video_id}/file")
async def get_video_file(video_id: str):
    """返回视频原始字节（用于迁移）"""
    try:
        service = get_video_metadata_service()
        video = await service.get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="视频不存在")

        file_path = service.video_dir / video.filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="视频文件不存在于服务器")

        def _iter():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        return StreamingResponse(
            _iter(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'inline; filename="{video.filename}"',
                "Cache-Control": "max-age=3600",
                "Content-Length": str(file_path.stat().st_size),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频文件失败 {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/videos/delete")
async def delete_videos(request: DeleteVideosRequest):
    """批量删除视频"""
    try:
        service = get_video_metadata_service()
        result = await service.delete_videos(request.video_ids)

        return {
            "success": True,
            "message": f"删除完成: 成功 {result['deleted']}, 失败 {result['failed']}",
            "data": result,
        }

    except Exception as e:
        logger.error(f"批量删除视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除视频失败: {str(e)}")


@router.post("/videos/{video_id}/tags")
async def update_tags(video_id: str, request: UpdateTagsRequest):
    """更新视频标签"""
    try:
        service = get_video_metadata_service()
        success = await service.update_tags(video_id, request.tags)

        if not success:
            raise HTTPException(status_code=404, detail="视频不存在")

        return {
            "success": True,
            "message": "标签更新成功",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新视频标签失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新视频标签失败: {str(e)}")


@router.post("/videos/{video_id}/favorite")
async def toggle_favorite(video_id: str, request: ToggleFavoriteRequest):
    """切换视频收藏状态"""
    try:
        service = get_video_metadata_service()
        success = await service.toggle_favorite(video_id, request.favorite)

        if not success:
            raise HTTPException(status_code=404, detail="视频不存在")

        return {
            "success": True,
            "message": "收藏状态更新成功",
            "data": {"favorite": request.favorite},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换收藏状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换收藏状态失败: {str(e)}")


@router.get("/tags")
async def get_tags():
    """获取所有标签列表"""
    try:
        service = get_video_metadata_service()
        tags = await service.get_all_tags()

        return {
            "success": True,
            "data": tags,
        }

    except Exception as e:
        logger.error(f"获取标签列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取标签列表失败: {str(e)}")


@router.get("/stats", response_model=VideoStats)
async def get_stats():
    """获取统计信息"""
    try:
        service = get_video_metadata_service()
        stats = await service.get_stats()

        return stats

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/check-missing")
async def check_missing_files():
    """检查哪些视频的文件已被删除（但元数据还在）"""
    try:
        service = get_video_metadata_service()
        result = await service.check_missing_files()

        return {
            "success": True,
            "message": f"检查完成: 总计 {result['total']}, 有效 {result['valid']}, 失效 {result['missing']}",
            "data": result,
        }
    except Exception as e:
        logger.error(f"检查失效视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查失效视频失败: {str(e)}")


@router.post("/cleanup")
async def cleanup_orphaned_metadata():
    """清理孤立的元数据（文件不存在但元数据还在）"""
    try:
        service = get_video_metadata_service()
        removed = await service.cleanup_orphaned_metadata()

        return {
            "success": True,
            "message": f"清理完成: 移除 {removed} 条孤立元数据",
            "data": {"removed": removed},
        }

    except Exception as e:
        logger.error(f"清理孤立元数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理孤立元数据失败: {str(e)}")
