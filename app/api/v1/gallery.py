"""
图片管理 API 路由
"""

import io
import zipfile
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.logger import logger
from app.services.gallery import (
    ImageMetadataService,
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


class ExportImagesRequest(BaseModel):
    """批量导出图片请求"""
    image_ids: List[str]


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


@router.post("/images/export")
async def export_images(request: ExportImagesRequest):
    """
    批量导出图片（ZIP）
    """
    try:
        service = get_image_metadata_service()

        # 创建内存中的 ZIP 文件
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for image_id in request.image_ids:
                # 获取图片元数据
                image = await service.get_image(image_id)
                if not image:
                    continue

                # 读取图片文件
                file_path = service.image_dir / image.filename
                if not file_path.exists():
                    continue

                # 添加到 ZIP
                zip_file.write(file_path, arcname=image.filename)

        # 重置缓冲区位置
        zip_buffer.seek(0)

        # 返回 ZIP 文件
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=images_export.zip"
            },
        )

    except Exception as e:
        logger.error(f"批量导出图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量导出图片失败: {str(e)}")
