"""
图片管理 API 路由
"""

import io
import zipfile
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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


class ImportImageRequest(BaseModel):
    """导入图片请求"""
    source_path: str
    tags: Optional[List[str]] = None


class AnalyzeQualityRequest(BaseModel):
    """分析图片质量请求"""
    image_ids: Optional[List[str]] = None
    update_metadata: bool = True
    batch_size: int = 50
    skip_analyzed: bool = False
    max_workers: int = Field(default=8, ge=1, le=16)


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


@router.post("/import")
async def import_image(request: ImportImageRequest):
    """
    从指定路径导入图片
    """
    try:
        service = get_image_metadata_service()
        image_id = await service.import_image(request.source_path, request.tags)

        if not image_id:
            raise HTTPException(status_code=400, detail="导入图片失败")

        return {
            "success": True,
            "message": "导入图片成功",
            "data": {"image_id": image_id},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导入图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入图片失败: {str(e)}")


@router.post("/upload")
async def upload_image(
    file: bytes = None,
    filename: str = None,
    tags: Optional[str] = None,
):
    """
    上传图片文件
    """
    try:
        from fastapi import File, UploadFile, Form
        import tempfile

        service = get_image_metadata_service()

        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp_file:
            tmp_file.write(file)
            tmp_path = tmp_file.name

        try:
            # 导入图片
            tag_list = tags.split(",") if tags else ["上传"]
            image_id = await service.import_image(tmp_path, tag_list)

            if not image_id:
                raise HTTPException(status_code=400, detail="上传图片失败")

            return {
                "success": True,
                "message": "上传图片成功",
                "data": {"image_id": image_id},
            }
        finally:
            # 清理临时文件
            Path(tmp_path).unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传图片失败: {e}")
        raise HTTPException(status_code=500, detail=f"上传图片失败: {str(e)}")


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
    min_quality_score: Optional[float] = Query(None, description="最低质量分数筛选"),
    max_quality_score: Optional[float] = Query(None, description="最高质量分数筛选"),
    has_quality_issues: Optional[bool] = Query(None, description="是否筛选有质量问题的图片"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序顺序（asc/desc）"),
):
    """
    获取图片列表（支持分页、筛选、排序）
    """
    try:
        service = get_image_metadata_service()

        # 调试日志
        logger.info(f"API 接收参数: min_quality_score={min_quality_score}, max_quality_score={max_quality_score}")

        # 构建筛选条件
        filters = ImageFilter(
            search=search,
            model=model,
            aspect_ratio=aspect_ratio,
            tags=tags.split(",") if tags else None,
            start_date=start_date,
            end_date=end_date,
            nsfw=nsfw,
            min_quality_score=min_quality_score,
            max_quality_score=max_quality_score,
            has_quality_issues=has_quality_issues,
        )

        # 调试日志
        logger.info(f"构建的筛选条件: {filters}")

        # 获取图片列表
        result = await service.list_images(
            filters=filters,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # 调试日志
        logger.info(f"返回结果: total={result.total}, images_count={len(result.images)}")

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


@router.post("/analyze-quality")
async def analyze_quality(request: AnalyzeQualityRequest):
    """
    批量分析图片质量
    """
    try:
        service = get_image_metadata_service()
        result = await service.batch_analyze_quality(
            image_ids=request.image_ids,
            update_metadata=request.update_metadata,
            batch_size=request.batch_size,
            skip_analyzed=request.skip_analyzed,
            max_workers=request.max_workers,
        )

        return {
            "success": True,
            "message": f"分析完成: 成功 {result['analyzed']}, 失败 {result['failed']}, 低质量 {result['low_quality_count']}",
            "data": result,
        }

    except Exception as e:
        logger.error(f"批量分析图片质量失败: {e}")
        raise HTTPException(status_code=500, detail=f"批量分析图片质量失败: {str(e)}")


@router.get("/images/{image_id}/quality")
async def get_image_quality(image_id: str):
    """
    获取单张图片的质量分析
    """
    try:
        service = get_image_metadata_service()
        result = await service.analyze_image_quality(image_id)

        if not result:
            raise HTTPException(status_code=404, detail="图片不存在或分析失败")

        return {
            "success": True,
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取图片质量失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图片质量失败: {str(e)}")
