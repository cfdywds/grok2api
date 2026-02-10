"""
Prompt Optimization API
"""

import orjson
from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.grok.services.chat import GrokChatService
from app.services.token import get_token_manager, EffortType
from app.services.grok.models.model import ModelService
from app.core.exceptions import ValidationException, AppException, ErrorType
from app.core.logger import logger


router = APIRouter(tags=["Prompt"])


class PromptOptimizeRequest(BaseModel):
    """提示词优化请求"""
    prompt: str = Field(..., description="原始提示词")
    context: str = Field(..., description="使用场景: imagine 或 img2img")
    language: Optional[str] = Field("auto", description="语言提示")


class PromptOptimizeResponse(BaseModel):
    """提示词优化响应"""
    original_prompt: str = Field(..., description="原始提示词")
    optimized_prompt: str = Field(..., description="优化后的提示词")
    explanation: str = Field(..., description="优化说明")
    improvements: List[str] = Field(..., description="改进点列表")


def build_system_prompt(context: str) -> str:
    """构建系统提示词"""
    base_principles = """You are a professional AI image generation prompt optimizer. Your task is to transform user's simple prompts into detailed, effective prompts that produce better results.

**Core Principles:**
1. Always output in English (English prompts work better)
2. Be specific and detailed
3. Use professional terminology
4. Structure: [Scene] + [Subject/Action] + [Details] + [Style/Atmosphere]
5. Include lighting, atmosphere, and mood descriptions

**Output Format:**
Return a JSON object with these fields:
- optimized_prompt: The optimized English prompt
- explanation: Brief explanation of what you changed
- improvements: Array of specific improvements made

**Important:**
- Keep the core intent of the original prompt
- Add details that enhance quality without changing the main subject
- Use concrete, visual descriptions
"""

    if context == "imagine":
        specific_guidance = """
**For Image Generation (Imagine):**
- Create complete scene descriptions
- Include composition details (angle, framing, perspective)
- Specify artistic style or photography type
- Add emotional and atmospheric descriptions
- Example: "未来城市" → "Futuristic cyberpunk cityscape at night, neon lights reflecting on wet streets, wide-angle shot from elevated perspective, cinematic lighting, moody atmosphere with purple and blue tones, highly detailed architecture"
"""
    else:  # img2img
        specific_guidance = """
**For Image Editing (Img2img):**
- Clearly state what to CHANGE (background, clothing, lighting, etc.)
- Clearly state what to KEEP (face, pose, expression, etc.)
- Use editing instruction prefixes: "Change...", "Transform...", "Edit..."
- Be explicit about the expected transformation
- Example: "换成泳装，背景改成海滩" → "Change clothing to swimsuit (bikini or one-piece). Change background to tropical beach with white sand and turquoise water. Keep person's face, pose, and expression exactly the same. Natural daylight, summer vacation atmosphere."
"""

    return base_principles + specific_guidance


async def optimize_prompt_with_grok(
    token: str,
    original_prompt: str,
    context: str,
) -> dict:
    """使用 Grok API 优化提示词"""
    system_prompt = build_system_prompt(context)

    user_message = f"""Original prompt: {original_prompt}

Please optimize this prompt following the guidelines. Return ONLY a valid JSON object, no additional text."""

    full_message = f"{system_prompt}\n\n{user_message}"

    # 调用 Grok Chat API
    # 注意：使用grok-3模型，因为tokens可能不支持grok-2-1212
    chat_service = GrokChatService()
    response = await chat_service.chat(
        token=token,
        message=full_message,
        model="grok-3",
        mode=None,
        stream=True,
    )

    # 收集响应
    collected_text = []
    async for line in response:
        line = line.strip()
        if not line:
            continue

        # 解析 SSE 格式
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break

            try:
                data = orjson.loads(data_str)
                if "choices" in data:
                    for choice in data["choices"]:
                        if "delta" in choice and "content" in choice["delta"]:
                            content = choice["delta"]["content"]
                            if content:
                                collected_text.append(content)
            except Exception as e:
                logger.debug(f"Failed to parse line: {e}")
                continue

    full_response = "".join(collected_text)
    logger.debug(f"Grok response: {full_response[:200]}...")

    # 解析 JSON 响应
    try:
        # 尝试提取 JSON 对象
        json_start = full_response.find("{")
        json_end = full_response.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = full_response[json_start:json_end]
            result = orjson.loads(json_str)

            # 验证必需字段
            if "optimized_prompt" in result:
                return {
                    "optimized_prompt": result.get("optimized_prompt", ""),
                    "explanation": result.get("explanation", "Optimized for better results"),
                    "improvements": result.get("improvements", ["Translated to English", "Added details"])
                }
    except Exception as e:
        logger.warning(f"Failed to parse JSON response: {e}")

    # 降级处理：如果 JSON 解析失败，返回原始响应
    return {
        "optimized_prompt": full_response.strip() or original_prompt,
        "explanation": "Optimization completed",
        "improvements": ["Enhanced prompt structure"]
    }


@router.post("/prompt/optimize", response_model=PromptOptimizeResponse)
async def optimize_prompt(request: PromptOptimizeRequest):
    """
    优化提示词

    将简单的提示词转换为详细、专业的提示词，提升图片生成质量。
    """
    # 参数验证
    if not request.prompt or not request.prompt.strip():
        raise ValidationException(
            message="Prompt cannot be empty",
            param="prompt",
            code="empty_prompt"
        )

    if request.context not in ["imagine", "img2img"]:
        raise ValidationException(
            message="Context must be 'imagine' or 'img2img'",
            param="context",
            code="invalid_context"
        )

    # 获取 token
    token_mgr = await get_token_manager()
    await token_mgr.reload_if_stale()

    token = None
    for pool_name in ModelService.pool_candidates_for_model("grok-2-1212"):
        token = token_mgr.get_token(pool_name)
        if token:
            break

    if not token:
        raise AppException(
            message="No available tokens. Please try again later.",
            error_type=ErrorType.RATE_LIMIT.value,
            code="rate_limit_exceeded",
            status_code=429,
        )

    # 调用优化服务
    try:
        result = await optimize_prompt_with_grok(
            token=token,
            original_prompt=request.prompt,
            context=request.context,
        )

        # 消耗 token（低消耗）
        try:
            await token_mgr.consume(token, EffortType.LOW)
        except Exception as e:
            logger.warning(f"Failed to consume token: {e}")

        return PromptOptimizeResponse(
            original_prompt=request.prompt,
            optimized_prompt=result["optimized_prompt"],
            explanation=result["explanation"],
            improvements=result["improvements"]
        )

    except Exception as e:
        logger.error(f"Prompt optimization failed: {e}")
        raise AppException(
            message="Prompt optimization failed",
            error_type=ErrorType.SERVER.value,
            code="optimization_failed",
            status_code=500,
        )


__all__ = ["router"]
