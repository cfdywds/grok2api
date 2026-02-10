"""
图片管理备份 API 路由
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.gallery.backup import get_backup_service
from app.core.logger import logger


router = APIRouter(tags=["Gallery Backup"])


class BackupInfo(BaseModel):
    """备份信息"""
    filename: str
    path: str
    size: int
    created_at: str
    reason: str
    timestamp: str


class BackupListResponse(BaseModel):
    """备份列表响应"""
    backups: List[BackupInfo]
    total: int


class CreateBackupRequest(BaseModel):
    """创建备份请求"""
    reason: Optional[str] = Field("manual", description="备份原因")


class RestoreBackupRequest(BaseModel):
    """恢复备份请求"""
    filename: str = Field(..., description="备份文件名")


@router.get("/backups", response_model=BackupListResponse)
async def list_backups(limit: int = 50):
    """
    列出所有备份

    Args:
        limit: 最多返回的备份数量
    """
    try:
        backup_service = get_backup_service()
        backups = backup_service.list_backups(limit=limit)

        return BackupListResponse(
            backups=[BackupInfo(**b) for b in backups],
            total=len(backups)
        )

    except Exception as e:
        logger.error(f"列出备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups")
async def create_backup(request: CreateBackupRequest):
    """
    手动创建备份

    Args:
        request: 创建备份请求
    """
    try:
        backup_service = get_backup_service()
        backup_path = backup_service.create_backup(reason=request.reason)

        if backup_path:
            return {
                "success": True,
                "message": "备份创建成功",
                "filename": backup_path.name,
                "path": str(backup_path)
            }
        else:
            raise HTTPException(status_code=500, detail="备份创建失败")

    except Exception as e:
        logger.error(f"创建备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/restore")
async def restore_backup(request: RestoreBackupRequest):
    """
    恢复备份

    Args:
        request: 恢复备份请求
    """
    try:
        backup_service = get_backup_service()
        success = backup_service.restore_backup(request.filename)

        if success:
            return {
                "success": True,
                "message": f"备份恢复成功: {request.filename}"
            }
        else:
            raise HTTPException(status_code=500, detail="备份恢复失败")

    except Exception as e:
        logger.error(f"恢复备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backups/cleanup")
async def cleanup_backups():
    """清理旧备份"""
    try:
        backup_service = get_backup_service()
        backup_service.cleanup_old_backups()

        return {
            "success": True,
            "message": "清理旧备份成功"
        }

    except Exception as e:
        logger.error(f"清理备份失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
