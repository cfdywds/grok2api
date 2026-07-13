"""
Copilot 图片助手服务

核心编排：LM Studio 对话 → 意图识别 → 图片生成 → 回复组装
"""

import base64
import time
import orjson
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from app.core.config import get_config
from app.core.logger import logger
from app.core.storage import DATA_DIR
from app.services.grok.services.image import image_service
from app.services.grok.models.model import ModelService
from app.services.token import get_token_manager, EffortType

from .lmstudio import LMStudioClient
from .memory import CopilotMemory
from .models import CopilotMessage


# 全局单例
_instance: Optional["CopilotService"] = None


def get_copilot_service() -> "CopilotService":
    """获取 CopilotService 单例"""
    global _instance
    if _instance is None:
        _instance = CopilotService()
    return _instance


SYSTEM_PROMPT = """你是一个 AI 图片创作助手。你同时具备聊天和图片生成两种能力。

## 你的职责
1. 和用户自然聊天，回答问题
2. 当用户想要生成或修改图片时，将需求转化为专业的英文图片生成 Prompt

## 判断规则
- 用户明确要求画图、生成图片、创作图片、画个XX → 生成模式
- 用户要求修改上一张图片（换背景、换颜色、调整细节等）→ 编辑模式
- 其他情况 → 普通聊天模式

## 生成模式的输出格式
当判定为图片生成需求时，你**必须且只能**输出以下 JSON（不要包含任何其他文本）：
```json
{"action": "generate", "prompt": "<专业的英文图片描述>", "comment": "<给用户的中文简要说明>"}
```

## 编辑模式的输出格式
当用户要求基于上一张图片修改时，你**必须且只能**输出以下 JSON：
```json
{"action": "edit", "prompt": "<修改后的完整英文图片描述>", "comment": "<给用户的中文修改说明>"}
```

## Prompt 编写原则
1. 始终使用英文编写 prompt
2. 结构：[场景] + [主体/动作] + [细节] + [风格/氛围]
3. 包含光照、氛围、情绪描写
4. 具体、详细、使用专业术语
5. 编辑模式下保留上一次 prompt 的优秀部分，只修改用户要求的部分

## 普通聊天模式
直接用自然语言回复用户，不要输出 JSON。"""


class CopilotService:
    """Copilot 图片助手核心服务"""

    def __init__(self):
        self.lmstudio = LMStudioClient()
        self.memory = CopilotMemory()
        self._image_dir: Optional[Path] = None

    def _ensure_image_dir(self) -> Path:
        """确保图片存储目录存在"""
        if self._image_dir is None:
            d = DATA_DIR / "tmp" / "image"
            d.mkdir(parents=True, exist_ok=True)
            self._image_dir = d
        return self._image_dir

    def _build_file_url(self, filename: str) -> str:
        """构建图片访问 URL（使用相对路径，确保前端加载不受 app_url 配置影响）"""
        return f"/v1/files/image/{filename}"

    @staticmethod
    def _stage_priority(stage: str) -> int:
        """图片阶段优先级：final > medium > preview"""
        return {"final": 3, "medium": 2, "preview": 1}.get(stage, 0)

    @staticmethod
    def _strip_base64_prefix(blob: str) -> str:
        """去除 data URL 前缀"""
        if "," in blob and "base64" in blob.split(",", 1)[0]:
            return blob.split(",", 1)[1]
        return blob

    def _decode_image_blob(self, blob: str) -> bytes:
        """解码图片 base64 数据"""
        return base64.b64decode(self._strip_base64_prefix(blob))

    @staticmethod
    def _normalize_quotes(text: str) -> str:
        """将中文/智能引号替换为标准 ASCII 引号，修复小模型输出的非标准 JSON"""
        replacements = {
            "\u201c": '"',  # "
            "\u201d": '"',  # "
            "\u2018": "'",  # '
            "\u2019": "'",  # '
            "\uff02": '"',  # ＂
            "\u300c": '"',  # 「
            "\u300d": '"',  # 」
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _parse_action(self, text: str) -> Optional[Dict]:
        """
        解析 LM Studio 回复中的 JSON action

        Returns:
            解析成功返回 dict，普通聊天返回 None
        """
        text = text.strip()

        # 先标准化引号
        normalized = self._normalize_quotes(text)

        # 尝试直接解析（原始 + 标准化）
        for candidate in [text, normalized]:
            try:
                data = orjson.loads(candidate)
                if isinstance(data, dict) and data.get("action") in ("generate", "edit"):
                    return data
            except Exception:
                pass

        # 尝试从 markdown code block 中提取
        for candidate in [text, normalized]:
            if "```json" in candidate:
                try:
                    json_str = candidate.split("```json")[1].split("```")[0].strip()
                    data = orjson.loads(json_str)
                    if isinstance(data, dict) and data.get("action") in (
                        "generate",
                        "edit",
                    ):
                        return data
                except Exception:
                    pass
            elif "```" in candidate:
                try:
                    json_str = candidate.split("```")[1].split("```")[0].strip()
                    data = orjson.loads(json_str)
                    if isinstance(data, dict) and data.get("action") in (
                        "generate",
                        "edit",
                    ):
                        return data
                except Exception:
                    pass

        # 尝试从 { 到 } 提取
        for candidate in [text, normalized]:
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end > start:
                try:
                    data = orjson.loads(candidate[start : end + 1])
                    if isinstance(data, dict) and data.get("action") in (
                        "generate",
                        "edit",
                    ):
                        return data
                except Exception:
                    pass

        return None

    async def _get_token_for_image(self) -> Tuple:
        """获取图片生成所需的 token"""
        model = get_config("copilot.image_model", "grok-imagine-1.0")
        token_mgr = await get_token_manager()
        await token_mgr.reload_if_stale()

        token = None
        for pool_name in ModelService.pool_candidates_for_model(model):
            token = token_mgr.get_token(pool_name)
            if token:
                break

        if not token:
            raise RuntimeError("没有可用的 Token 用于图片生成")

        return token_mgr, token

    async def _collect_best_images(
        self,
        token: str,
        prompt: str,
        aspect_ratio: str,
        n: int,
        enable_nsfw: bool,
    ) -> Dict[str, Dict]:
        """单次请求收集最佳图片（同一 image_id 取最高阶段/最大尺寸）"""
        best_images: Dict[str, Dict] = {}

        async for event in image_service.stream(
            token, prompt, aspect_ratio, n, enable_nsfw
        ):
            if event.get("type") != "image":
                continue

            stage = event.get("stage", "preview")
            blob = event.get("blob", "")
            if not blob:
                continue

            image_id = event.get("image_id") or event.get(
                "imageId", f"copilot_{int(time.time() * 1000)}"
            )
            blob_size = event.get("blob_size", event.get("blobSize", len(blob)))
            try:
                blob_size = int(blob_size)
            except (TypeError, ValueError):
                blob_size = len(blob)

            existing = best_images.get(image_id)
            current_priority = self._stage_priority(stage)

            if existing:
                existing_priority = self._stage_priority(existing["stage"])
                if current_priority < existing_priority:
                    continue
                if (
                    current_priority == existing_priority
                    and blob_size <= existing.get("blob_size", 0)
                ):
                    continue

            best_images[image_id] = {
                "image_id": image_id,
                "stage": stage,
                "blob": blob,
                "blob_size": blob_size,
            }
            logger.debug(
                f"CopilotService: 收到图片 {image_id} stage={stage} size={blob_size}"
            )

        return best_images

    def _save_valid_images(
        self, best_images: Dict[str, Dict], min_bytes: int, limit: int
    ) -> List[str]:
        """保存符合最小字节数要求的图片"""
        image_dir = self._ensure_image_dir()
        valid_images = []

        for image_id, img_data in best_images.items():
            try:
                payload = self._decode_image_blob(img_data["blob"])
            except Exception as e:
                logger.warning(
                    f"CopilotService: 图片解码失败 {image_id}, error={e}"
                )
                continue

            file_size = len(payload)
            if file_size < min_bytes:
                logger.warning(
                    f"CopilotService: 过滤小图 {image_id} "
                    f"(stage={img_data['stage']}, size={file_size}B < {min_bytes}B)"
                )
                continue

            valid_images.append(
                {
                    "image_id": image_id,
                    "stage": img_data["stage"],
                    "payload": payload,
                    "file_size": file_size,
                }
            )

        valid_images.sort(
            key=lambda item: (
                self._stage_priority(item["stage"]),
                item["file_size"],
            ),
            reverse=True,
        )
        if limit:
            valid_images = valid_images[:limit]

        image_urls = []
        for item in valid_images:
            is_final = item["stage"] == "final"
            ext = "jpg" if is_final else "png"
            filename = f"{item['image_id']}.{ext}"
            filepath = image_dir / filename

            with open(filepath, "wb") as f:
                f.write(item["payload"])

            if filepath.exists() and filepath.stat().st_size > 0:
                url = self._build_file_url(filename)
                image_urls.append(url)
                logger.info(
                    f"CopilotService: 图片已保存 {filepath} "
                    f"(stage={item['stage']}, size={filepath.stat().st_size}B)"
                )
            else:
                logger.error(f"CopilotService: 图片文件写入失败 {filepath}")

        return image_urls

    async def _generate_images(self, prompt: str) -> List[str]:
        """
        调用 Grok 图片生成服务

        Returns:
            图片 URL 列表
        """
        n = get_config("copilot.image_n", 1)
        aspect_ratio = get_config("copilot.image_aspect_ratio", "1:1")
        enable_nsfw = get_config("image.image_ws_nsfw", True)
        min_bytes = max(1, int(get_config("copilot.image_min_bytes", 50000)))
        max_attempts = max(1, int(get_config("copilot.image_max_attempts", 10)))

        token_mgr, token = await self._get_token_for_image()
        last_error: Optional[Exception] = None

        try:
            for attempt in range(1, max_attempts + 1):
                logger.info(
                    f"CopilotService: 对话生图尝试 {attempt}/{max_attempts}, "
                    f"min_bytes={min_bytes}"
                )
                best_images = await self._collect_best_images(
                    token, prompt, aspect_ratio, n, enable_nsfw
                )

                try:
                    await token_mgr.consume(token, EffortType.HIGH)
                except Exception as e:
                    logger.warning(f"Failed to consume token: {e}")

                image_urls = self._save_valid_images(best_images, min_bytes, n)
                if image_urls:
                    return image_urls

                logger.warning(
                    f"CopilotService: 第 {attempt}/{max_attempts} 次对话生图未拿到 "
                    f">= {min_bytes}B 的正常图片，准备重试"
                )

            raise RuntimeError(
                f"连续 {max_attempts} 次生成后，仍未拿到大于等于 {min_bytes}B 的正常图片"
            )
        except Exception as e:
            last_error = e
            logger.error(f"CopilotService: 图片生成失败: {e}")
            raise
        finally:
            if last_error:
                logger.debug(
                    f"CopilotService: 最后一次失败原因: {last_error.__class__.__name__}"
                )

    def _build_reply(
        self, comment: str, image_urls: List[str], prompt: str
    ) -> str:
        """组装图片生成回复"""
        parts = [comment, ""]
        for url in image_urls:
            parts.append(f"![generated image]({url})")
            parts.append("")
        parts.append(f"> Prompt: *{prompt}*")
        return "\n".join(parts)

    async def chat(
        self,
        session_id: Optional[str],
        user_message: str,
        stream: bool = True,
    ):
        """
        核心对话方法

        Args:
            session_id: 会话 ID，None 则新建
            user_message: 用户消息
            stream: 是否流式输出

        Returns:
            非流式: (session_id, reply_text)
            流式: (session_id, AsyncGenerator)
        """
        # 1. 获取或创建会话
        session = await self.memory.get_or_create(session_id)

        # 2. 保存用户消息
        user_msg = CopilotMessage(role="user", content=user_message)
        await self.memory.add_message(session.id, user_msg)

        # 3. 拼接完整消息列表
        history = await self.memory.get_history_messages(session.id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        if stream:
            return session.id, self._chat_stream(session.id, messages)
        else:
            return session.id, await self._chat_non_stream(session.id, messages)

    async def _chat_non_stream(
        self, session_id: str, messages: List[Dict]
    ) -> str:
        """非流式对话"""
        # 调用 LM Studio
        response_text = await self.lmstudio.chat(messages)

        # 解析意图
        action = self._parse_action(response_text)

        if action and action.get("action") in ("generate", "edit"):
            prompt = action.get("prompt", "")
            comment = action.get("comment", "正在为你生成图片...")

            # 生成图片
            try:
                image_urls = await self._generate_images(prompt)
            except Exception as e:
                reply = f"{comment}\n\n图片生成失败: {e}"
                await self.memory.add_message(
                    session_id,
                    CopilotMessage(role="assistant", content=reply),
                )
                return reply

            # 组装回复
            reply = self._build_reply(comment, image_urls, prompt)

            # 保存助手消息
            await self.memory.add_message(
                session_id,
                CopilotMessage(
                    role="assistant",
                    content=reply,
                    image_urls=image_urls,
                    image_prompt=prompt,
                ),
            )
            return reply
        else:
            # 普通聊天
            await self.memory.add_message(
                session_id,
                CopilotMessage(role="assistant", content=response_text),
            )
            return response_text

    async def _chat_stream(
        self, session_id: str, messages: List[Dict]
    ) -> AsyncGenerator[str, None]:
        """
        流式对话

        策略：先用非流式调用 LM Studio 获取完整回复判断意图，
        然后根据意图决定是直接流式返回文本还是生成图片。
        """
        # 非流式获取完整回复以判断意图
        response_text = await self.lmstudio.chat(messages)
        action = self._parse_action(response_text)

        if action and action.get("action") in ("generate", "edit"):
            prompt = action.get("prompt", "")
            comment = action.get("comment", "正在为你生成图片...")

            # 先流式输出 comment
            yield comment
            yield "\n\n"
            yield "正在生成图片，请稍候...\n\n"

            # 生成图片
            try:
                image_urls = await self._generate_images(prompt)
            except Exception as e:
                error_msg = f"图片生成失败: {e}"
                yield error_msg
                await self.memory.add_message(
                    session_id,
                    CopilotMessage(
                        role="assistant", content=f"{comment}\n\n{error_msg}"
                    ),
                )
                return

            # 输出图片链接
            for url in image_urls:
                yield f"![generated image]({url})\n\n"

            yield f"> Prompt: *{prompt}*"

            # 保存到记忆
            reply = self._build_reply(comment, image_urls, prompt)
            await self.memory.add_message(
                session_id,
                CopilotMessage(
                    role="assistant",
                    content=reply,
                    image_urls=image_urls,
                    image_prompt=prompt,
                ),
            )
        else:
            # 普通聊天 - 直接输出已获取的文本（避免重复调用 LM Studio）
            yield response_text

            # 保存完整回复到记忆
            await self.memory.add_message(
                session_id,
                CopilotMessage(role="assistant", content=response_text),
            )

    async def close(self):
        """清理资源"""
        await self.lmstudio.close()
