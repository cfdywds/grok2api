"""
Prompt Optimization API
"""

import orjson
from typing import Optional, List
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.grok.services.chat import ChatService
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
    original_prompt: str,
    context: str,
) -> dict:
    """使用 Grok API 优化提示词（非流式，OpenAI 兼容格式）"""
    system_prompt = build_system_prompt(context)
    user_message = f"""Original prompt: {original_prompt}

Please optimize this prompt following the guidelines. Return ONLY a valid JSON object, no additional text."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # 使用 ChatService.completions 非流式模式，自动处理 token 选择和格式转换
    result = await ChatService.completions(
        model="grok-3",
        messages=messages,
        stream=False,
    )

    # 提取文本内容（OpenAI 非流式格式：choices[0].message.content）
    full_response = ""
    try:
        full_response = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"Failed to extract content from response: {e}, result={str(result)[:200]}")

    logger.debug(f"Grok response: {full_response[:200]}...")

    # 解析 JSON 响应
    if full_response:
        try:
            json_start = full_response.find("{")
            json_end = full_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = full_response[json_start:json_end]
                parsed = orjson.loads(json_str)
                if "optimized_prompt" in parsed:
                    return {
                        "optimized_prompt": parsed.get("optimized_prompt", ""),
                        "explanation": parsed.get("explanation", "Optimized for better results"),
                        "improvements": parsed.get("improvements", ["Translated to English", "Added details"]),
                    }
        except Exception as e:
            logger.warning(f"Failed to parse JSON response: {e}")

    # 降级处理：JSON 解析失败时返回原始响应文本
    return {
        "optimized_prompt": full_response.strip() or original_prompt,
        "explanation": "Optimization completed",
        "improvements": ["Enhanced prompt structure"],
    }


@router.post("/prompt/optimize", response_model=PromptOptimizeResponse)
async def optimize_prompt(request: PromptOptimizeRequest):
    """
    优化提示词

    将简单的提示词转换为详细、专业的提示词，提升图片生成质量。
    """
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

    try:
        result = await optimize_prompt_with_grok(
            original_prompt=request.prompt,
            context=request.context,
        )
        return PromptOptimizeResponse(
            original_prompt=request.prompt,
            optimized_prompt=result["optimized_prompt"],
            explanation=result["explanation"],
            improvements=result["improvements"],
        )
    except AppException:
        raise
    except Exception as e:
        logger.error(f"Prompt optimization failed: {e}")
        raise AppException(
            message="Prompt optimization failed",
            error_type=ErrorType.SERVER.value,
            code="optimization_failed",
            status_code=500,
        )


__all__ = ["router"]
