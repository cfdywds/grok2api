"""提示词管理 API"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from app.services.prompts.service import PromptService
from app.services.prompts.models import (
    Prompt,
    PromptCreate,
    PromptUpdate,
    PromptList,
)
from app.core.logger import logger

router = APIRouter(prefix="/api/v1/admin/prompts", tags=["prompts"])


@router.get("/list", response_model=PromptList)
async def get_prompts(
    category: Optional[str] = Query(None, description="分类筛选"),
    tag: Optional[str] = Query(None, description="标签筛选"),
    favorite: Optional[bool] = Query(None, description="收藏筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取提示词列表"""
    try:
        service = PromptService()
        return await service.get_all_prompts(
            category=category,
            tag=tag,
            favorite=favorite,
            search=search,
        )
    except Exception as e:
        logger.error(f"获取提示词列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{prompt_id}", response_model=Prompt)
async def get_prompt(prompt_id: str):
    """获取单个提示词"""
    try:
        service = PromptService()
        prompt = await service.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(status_code=404, detail="提示词不存在")
        return prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=Prompt)
async def create_prompt(prompt_data: PromptCreate):
    """创建提示词"""
    try:
        service = PromptService()
        return await service.create_prompt(prompt_data)
    except Exception as e:
        logger.error(f"创建提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{prompt_id}", response_model=Prompt)
async def update_prompt(prompt_id: str, prompt_data: PromptUpdate):
    """更新提示词"""
    try:
        service = PromptService()
        prompt = await service.update_prompt(prompt_id, prompt_data)
        if not prompt:
            raise HTTPException(status_code=404, detail="提示词不存在")
        return prompt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete")
async def delete_prompts(prompt_ids: List[str]):
    """删除提示词"""
    try:
        service = PromptService()
        deleted_count = await service.delete_prompts(prompt_ids)
        return {
            "success": True,
            "message": f"成功删除 {deleted_count} 个提示词",
            "deleted_count": deleted_count,
        }
    except Exception as e:
        logger.error(f"删除提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{prompt_id}/use")
async def use_prompt(prompt_id: str):
    """使用提示词（增加使用次数）"""
    try:
        service = PromptService()
        success = await service.increment_use_count(prompt_id)
        if not success:
            raise HTTPException(status_code=404, detail="提示词不存在")
        return {"success": True, "message": "使用次数已更新"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新使用次数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/all")
async def export_prompts():
    """导出所有提示词"""
    try:
        service = PromptService()
        data = await service.export_prompts()
        return data
    except Exception as e:
        logger.error(f"导出提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_prompts(data: dict, merge: bool = Query(True, description="是否合并")):
    """导入提示词"""
    try:
        service = PromptService()
        count = await service.import_prompts(data, merge=merge)
        return {
            "success": True,
            "message": f"成功导入 {count} 个提示词",
            "imported_count": count,
        }
    except Exception as e:
        logger.error(f"导入提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
