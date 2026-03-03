"""
图片管理 API 路由
"""

import random
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.logger import logger
from app.services.gallery import (
    ImageFilter,
    ImageListResponse,
    ImageStats,
)
from app.services.gallery.service import get_image_metadata_service


router = APIRouter(prefix="/api/v1/admin/gallery", tags=["Gallery"])


class DeleteImagesRequest(BaseModel):
    """批量删除图片请求"""
    image_ids: List[str]


class UpdateTagsRequest(BaseModel):
    """更新标签请求"""
    tags: List[str]


class ToggleFavoriteRequest(BaseModel):
    """切换收藏请求"""
    favorite: bool


@router.post("/scan")
async def scan_local_images():
    """
    扫描本地图片文件夹，为没有元数据的图片创建元数据
    """
    try:
        service = get_image_metadata_service()
        result = await service.scan_local_images()

        return {
            "success": True,
            "message": f"扫描完成: 新增 {result['added']}, 跳过 {result['skipped']}, 失败 {result['failed']}",
            "data": result,
        }

    except Exception as e:
        logger.error(f"扫描本地图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"扫描本地图片失败: {str(e)}")


@router.get("/images", response_model=ImageListResponse)
async def list_images(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    model: Optional[str] = Query(None, description="模型筛选"),
    aspect_ratio: Optional[str] = Query(None, description="宽高比筛选"),
    tags: Optional[str] = Query(None, description="标签筛选（逗号分隔）"),
    start_date: Optional[int] = Query(None, description="开始日期（时间戳）"),
    end_date: Optional[int] = Query(None, description="结束日期（时间戳）"),
    nsfw: Optional[bool] = Query(None, description="是否筛选敏感内容"),
    favorite: Optional[bool] = Query(None, description="是否筛选收藏的图片"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序顺序（asc/desc）"),
):
    """
    获取图片列表（支持分页、筛选、排序）
    """
    try:
        service = get_image_metadata_service()

        # 构建筛选条件
        filters = ImageFilter(
            search=search,
            model=model,
            aspect_ratio=aspect_ratio,
            tags=tags.split(",") if tags else None,
            start_date=start_date,
            end_date=end_date,
            nsfw=nsfw,
            favorite=favorite,
        )

        # 获取图片列表
        result = await service.list_images(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        return result

    except Exception as e:
        logger.error(f"获取图片列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图片列表失败: {str(e)}")


@router.get("/images/random")
async def get_random_image(
    exclude_ids: Optional[str] = Query(None, description="排除的图片ID列表（逗号分隔）"),
    min_quality_score: Optional[float] = Query(40, description="最低质量分数")
):
    """
    获取随机图片（根据质量分数加权）
    """
    try:
        service = get_image_metadata_service()

        # 获取所有图片
        data = await service.storage.load_image_metadata()
        images = data.get("images", [])

        # 解析排除的ID列表
        excluded_ids = set(exclude_ids.split(",")) if exclude_ids else set()

        # 过滤图片
        candidates = []
        weights = []

        for img in images:
            # 跳过已查看的图片
            if img.get("id") in excluded_ids:
                continue

            # 跳过质量分数低于阈值的图片
            quality_score = img.get("quality_score")
            if quality_score is None or quality_score < min_quality_score:
                continue

            # 根据质量分数设置权重
            if quality_score >= 80:
                weight = 3
            elif quality_score >= 60:
                weight = 2
            elif quality_score >= 40:
                weight = 1
            else:
                weight = 0.5

            candidates.append(img)
            weights.append(weight)

        # 如果没有符合条件的图片
        if not candidates:
            return {
                "success": False,
                "message": "没有符合条件的图片",
                "data": None
            }

        # 加权随机选择
        selected = random.choices(candidates, weights=weights, k=1)[0]

        # 添加文件路径信息
        selected["file_path"] = str(service.image_dir / selected["filename"])
        selected["relative_path"] = f"data/tmp/image/{selected['filename']}"

        return {
            "success": True,
            "data": selected
        }

    except Exception as e:
        logger.error(f"获取随机图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取随机图片失败: {str(e)}")


@router.get("/migrate")
async def get_migration_info():
    """获取服务端历史数据迁移信息"""
    try:
        service = get_image_metadata_service()
        stats = await service.get_stats()
        return {
            "success": True,
            "data": {
                "total": stats.total_count,
                "has_image_dir": service.image_dir.exists() if hasattr(service, "image_dir") else False,
            },
        }
    except Exception as e:
        logger.error(f"获取迁移信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/images/{image_id}/file")
async def get_image_file(image_id: str):
    """返回图片原始字节（用于迁移）"""
    try:
        service = get_image_metadata_service()
        image = await service.get_image(image_id)
        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        file_path = service.image_dir / image.filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="图片文件不存在于服务器")

        def _iter():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        return StreamingResponse(
            _iter(),
            media_type="image/jpeg",
            headers={
                "Content-Disposition": f'inline; filename="{image.filename}"',
                "Cache-Control": "max-age=3600",
                "Content-Length": str(file_path.stat().st_size),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取图片文件失败 {image_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/images/{image_id}")
async def get_image(image_id: str):
    """
    获取图片详情
    """
    try:
        service = get_image_metadata_service()
        image = await service.get_image(image_id)

        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        return image

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取图片详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图片详情失败: {str(e)}")


@router.post("/images/delete")
async def delete_images(request: DeleteImagesRequest):
    """
    批量删除图片
    """
    try:
        service = get_image_metadata_service()
        result = await service.delete_images(request.image_ids)

        return {
            "success": True,
            "message": f"删除完成: 成功 {result['deleted']}, 失败 {result['failed']}",
            "data": result,
        }

    except Exception as e:
        logger.error(f"批量删除图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量删除图片失败: {str(e)}")


@router.post("/images/{image_id}/tags")
async def update_tags(image_id: str, request: UpdateTagsRequest):
    """
    更新图片标签
    """
    try:
        service = get_image_metadata_service()
        success = await service.update_tags(image_id, request.tags)

        if not success:
            raise HTTPException(status_code=404, detail="图片不存在")

        return {
            "success": True,
            "message": "标签更新成功",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新图片标签失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新图片标签失败: {str(e)}")


@router.get("/tags")
async def get_tags():
    """
    获取所有标签列表
    """
    try:
        service = get_image_metadata_service()
        tags = await service.get_all_tags()

        return {
            "success": True,
            "data": tags,
        }

    except Exception as e:
        logger.error(f"获取标签列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取标签列表失败: {str(e)}")


@router.get("/stats", response_model=ImageStats)
async def get_stats():
    """
    获取统计信息
    """
    try:
        service = get_image_metadata_service()
        stats = await service.get_stats()

        return stats

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/check-missing")
async def check_missing_files():
    """
    检查哪些图片的文件已被删除（但元数据还在）
    """
    try:
        service = get_image_metadata_service()
        result = await service.check_missing_files()

        return {
            "success": True,
            "message": f"检查完成: 总计 {result['total']}, 有效 {result['valid']}, 失效 {result['missing']}",
            "data": result,
        }
    except Exception as e:
        logger.error(f"检查失效图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查失效图片失败: {str(e)}")


@router.post("/images/{image_id}/favorite")
async def toggle_favorite(image_id: str, request: ToggleFavoriteRequest):
    """
    切换图片收藏状态
    """
    try:
        service = get_image_metadata_service()
        success = await service.toggle_favorite(image_id, request.favorite)

        if not success:
            raise HTTPException(status_code=404, detail="图片不存在")

        return {
            "success": True,
            "message": "收藏状态更新成功",
            "data": {"favorite": request.favorite}
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"切换收藏状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换收藏状态失败: {str(e)}")
