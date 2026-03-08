"""
Novel Director REST API

路由前缀: /api/v1/admin/novel-director

提供角色管理、项目管理、场景管理和视频生成接口。
"""

from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Depends

from app.core.auth import verify_admin_session_or_app_key
from app.core.logger import logger
from app.services.novel_director import (
    CharacterProfile,
    Scene,
    StoryProject,
    NovelDirectorService,
    get_novel_director_service,
)
from app.services.novel_director.models import (
    CharacterCreate,
    CharacterUpdate,
    SceneCreate,
    SceneUpdate,
    ProjectCreate,
    ProjectUpdate,
    ReorderScenesRequest,
    BuildPromptRequest,
)
from app.services.grok.services.image import image_service
from app.services.grok.services.media import VideoService
from app.services.grok.models.model import ModelService
from app.services.token.manager import get_token_manager

router = APIRouter(prefix="/api/v1/admin/novel-director", tags=["Novel Director"])


def get_service() -> NovelDirectorService:
    return get_novel_director_service()


async def _get_token_for_model(model: str) -> str:
    """获取指定模型所需的 token"""
    token_mgr = await get_token_manager()
    await token_mgr.reload_if_stale()

    token = None
    for pool_name in ModelService.pool_candidates_for_model(model):
        token = token_mgr.get_token(pool_name)
        if token:
            break

    if not token:
        raise HTTPException(status_code=503, detail="No available tokens")
    return token, token_mgr


# ==================== 角色管理 ====================


@router.get("/characters", response_model=list[CharacterProfile])
async def list_characters(
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """获取所有角色"""
    return await service.list_characters()


@router.get("/characters/{character_id}", response_model=CharacterProfile)
async def get_character(
    character_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """获取单个角色"""
    char = await service.get_character(character_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return char


@router.post("/characters", response_model=CharacterProfile)
async def create_character(
    req: CharacterCreate,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """创建角色"""
    return await service.create_character(req)


@router.put("/characters/{character_id}", response_model=CharacterProfile)
async def update_character(
    character_id: str,
    req: CharacterUpdate,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """更新角色"""
    char = await service.update_character(character_id, req)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return char


@router.delete("/characters/{character_id}")
async def delete_character(
    character_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """删除角色"""
    success = await service.delete_character(character_id)
    if not success:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"success": True}


@router.post("/characters/{character_id}/generate-ref")
async def generate_character_reference(
    character_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """生成角色参考图（调用 Imagine API）"""
    char = await service.get_character(character_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")

    if not char.appearance:
        raise HTTPException(status_code=400, detail="角色缺少外貌描述")

    try:
        # 获取 token
        token, token_mgr = await _get_token_for_model("grok-imagine-1.0")

        # 调用图片生成服务
        final_image_url = None
        async for event in image_service.stream(
            token=token,
            prompt=char.appearance,
            aspect_ratio="1:1",
            n=1,
            enable_nsfw=False,
        ):
            if event.get("type") == "image" and event.get("stage") == "final":
                # 处理图片 URL
                blob = event.get("blob", "")
                if blob.startswith("data:"):
                    # base64 格式，需要保存
                    import base64
                    from app.services.grok.services.assets import UploadService

                    # 提取 base64 数据
                    mime_end = blob.index(";base64,")
                    mime = blob[5:mime_end]
                    b64_data = blob[mime_end + 8 :]

                    # 上传到资产服务
                    upload_service = UploadService()
                    image_bytes = base64.b64decode(b64_data)
                    final_image_url = await upload_service.upload_image(
                        token, image_bytes, "character_ref.jpg"
                    )
                else:
                    final_image_url = blob

                # 消耗 token
                from app.services.token import EffortType

                model_info = ModelService.get("grok-imagine-1.0")
                if model_info:
                    await token_mgr.consume(token, EffortType.HIGH)
                break
            elif event.get("type") == "error":
                raise HTTPException(
                    status_code=500, detail=event.get("error", "图片生成失败")
                )

        if not final_image_url:
            raise HTTPException(status_code=500, detail="图片生成失败，未获取到最终图片")

        # 更新角色的参考图
        update_req = CharacterUpdate(reference_image_url=final_image_url)
        await service.update_character(character_id, update_req)

        return {"success": True, "image_url": final_image_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate character reference failed: {e}")
        raise HTTPException(status_code=500, detail=f"生成参考图失败: {str(e)}")


# ==================== 项目管理 ====================


@router.get("/projects", response_model=list[StoryProject])
async def list_projects(
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """获取所有项目"""
    return await service.list_projects()


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """获取项目详情（含场景列表）"""
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    scenes = await service.list_scenes(project_id)

    # 获取项目涉及的所有角色
    character_ids = set()
    for scene in scenes:
        character_ids.update(scene.characters)

    characters = []
    for char_id in character_ids:
        char = await service.get_character(char_id)
        if char:
            characters.append(char)

    return {
        "project": project,
        "scenes": scenes,
        "characters": characters,
    }


@router.post("/projects", response_model=StoryProject)
async def create_project(
    req: ProjectCreate,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """创建项目"""
    return await service.create_project(req)


@router.put("/projects/{project_id}", response_model=StoryProject)
async def update_project(
    project_id: str,
    req: ProjectUpdate,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """更新项目"""
    project = await service.update_project(project_id, req)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """删除项目"""
    success = await service.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True}


# ==================== 场景管理 ====================


@router.get("/scenes/{scene_id}", response_model=Scene)
async def get_scene(
    scene_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """获取场景详情"""
    scene = await service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    return scene


@router.post("/scenes", response_model=Scene)
async def create_scene(
    req: SceneCreate,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """创建场景"""
    # 验证项目存在
    project = await service.get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=400, detail="项目不存在")

    return await service.create_scene(req)


@router.put("/scenes/{scene_id}", response_model=Scene)
async def update_scene(
    scene_id: str,
    req: SceneUpdate,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """更新场景"""
    scene = await service.update_scene(scene_id, req)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")
    return scene


@router.delete("/scenes/{scene_id}")
async def delete_scene(
    scene_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """删除场景"""
    success = await service.delete_scene(scene_id)
    if not success:
        raise HTTPException(status_code=404, detail="场景不存在")
    return {"success": True}


@router.post("/scenes/reorder")
async def reorder_scenes(
    req: ReorderScenesRequest,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """重排序场景"""
    success = await service.reorder_scenes(req.project_id, req.scene_ids)
    return {"success": success}


@router.post("/scenes/{scene_id}/build-prompt")
async def build_scene_prompt(
    scene_id: str,
    req: BuildPromptRequest = None,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """预览场景的组装 Prompt"""
    req = req or BuildPromptRequest()
    prompt = await service.build_scene_prompt(
        scene_id,
        style_preset=req.style_preset,
        include_narrative=req.include_narrative,
    )
    if not prompt:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 获取参考图
    ref_image = await service.get_scene_reference_image(scene_id)

    return {
        "prompt": prompt,
        "reference_image_url": ref_image,
    }


# ==================== 视频生成 ====================


@router.post("/scenes/{scene_id}/generate")
async def generate_scene_video(
    scene_id: str,
    service: NovelDirectorService = Depends(get_service),
    _: bool = Depends(verify_admin_session_or_app_key),
):
    """为场景生成视频"""
    scene = await service.get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 构建 Prompt
    prompt = await service.build_scene_prompt(scene_id)
    if not prompt:
        raise HTTPException(status_code=400, detail="无法生成 Prompt")

    # 获取参考图
    ref_image = await service.get_scene_reference_image(scene_id)

    # 获取项目设置
    project = await service.get_project(scene.project_id)
    aspect_ratio = project.aspect_ratio if project else "16:9"
    resolution = project.resolution if project else "720p"

    # 更新场景状态为 generating
    await service.update_scene(scene_id, SceneUpdate(status="generating"))

    try:
        # 获取 token
        token, token_mgr = await _get_token_for_model("grok-imagine-1.0-video")

        video_service = VideoService()
        video_url = None
        video_id = None

        if ref_image:
            # 图生视频
            stream = await video_service.generate_from_image(
                token=token,
                prompt=prompt,
                image_url=ref_image,
                aspect_ratio=aspect_ratio,
                resolution_name=resolution,
            )
        else:
            # 文生视频
            stream = await video_service.generate(
                token=token,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                resolution_name=resolution,
            )

        # 处理视频流
        from app.services.grok.processors.video_processors import VideoCollectProcessor

        processor = VideoCollectProcessor(model="grok-imagine-1.0-video", token=token)
        result = await processor.process(stream)

        video_url = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        if video_url and "<video" in video_url:
            # 提取视频 URL
            import re

            match = re.search(r'src="([^"]+)"', video_url)
            if match:
                video_url = match.group(1)

        # 消耗 token
        from app.services.token import EffortType

        await token_mgr.consume(token, EffortType.HIGH)

        if not video_url:
            raise Exception("视频生成失败，未获取到视频 URL")

        # 更新场景
        update_data = SceneUpdate(
            status="done",
            prompt_used=prompt,
            generated_video_url=video_url,
        )
        await service.update_scene(scene_id, update_data)

        return {
            "success": True,
            "video_url": video_url,
            "prompt": prompt,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        # 更新场景状态为 draft
        await service.update_scene(scene_id, SceneUpdate(status="draft"))
        raise HTTPException(status_code=500, detail=f"视频生成失败: {str(e)}")


# ==================== 辅助接口 ====================


@router.get("/moods")
async def list_moods(_: bool = Depends(verify_admin_session_or_app_key)):
    """获取可用的情绪氛围列表"""
    from app.services.novel_director.service import MOOD_MAP

    return [{"label": k, "value": v} for k, v in MOOD_MAP.items()]


@router.get("/cameras")
async def list_cameras(_: bool = Depends(verify_admin_session_or_app_key)):
    """获取可用的镜头语言列表"""
    from app.services.novel_director.service import CAMERA_MAP

    return [{"label": k, "value": v} for k, v in CAMERA_MAP.items()]


@router.get("/styles")
async def list_styles(_: bool = Depends(verify_admin_session_or_app_key)):
    """获取可用的风格预设列表"""
    from app.services.novel_director.service import STYLE_MAP

    return [{"label": k, "value": v} for k, v in STYLE_MAP.items()]
