"""
Copilot 会话记忆管理

支持多会话持久化、历史消息裁剪
"""

import time
from typing import Dict, List, Optional

from app.core.config import get_config
from app.core.logger import logger
from app.core.storage import get_storage

from .models import CopilotMessage, CopilotSession


class CopilotMemory:
    """会话记忆管理器"""

    async def _load_data(self) -> Dict:
        """加载所有 copilot 数据"""
        storage = get_storage()
        return await storage.load_copilot_data()

    async def _save_data(self, data: Dict):
        """保存所有 copilot 数据"""
        storage = get_storage()
        await storage.save_copilot_data(data)

    async def get_session(self, session_id: str) -> Optional[CopilotSession]:
        """获取指定会话"""
        data = await self._load_data()
        for s in data.get("sessions", []):
            if s.get("id") == session_id:
                return CopilotSession(**s)
        return None

    async def create_session(self) -> CopilotSession:
        """创建新会话"""
        session = CopilotSession()
        data = await self._load_data()
        sessions = data.get("sessions", [])
        sessions.append(session.model_dump())
        data["sessions"] = sessions
        await self._save_data(data)
        logger.info(f"CopilotMemory: 创建会话 {session.id}")
        return session

    async def get_or_create(self, session_id: Optional[str]) -> CopilotSession:
        """获取或创建会话"""
        if session_id:
            session = await self.get_session(session_id)
            if session:
                return session
        return await self.create_session()

    async def add_message(self, session_id: str, message: CopilotMessage):
        """向会话追加消息"""
        storage = get_storage()
        async with storage.acquire_lock("copilot_data", timeout=5):
            data = await self._load_data()
            sessions = data.get("sessions", [])

            for i, s in enumerate(sessions):
                if s.get("id") == session_id:
                    messages = s.get("messages", [])
                    messages.append(message.model_dump())
                    s["messages"] = messages
                    s["updated_at"] = time.time()

                    # 自动生成标题（取首条用户消息前 20 字）
                    if not s.get("title"):
                        for m in messages:
                            if m.get("role") == "user":
                                s["title"] = m["content"][:20]
                                break

                    sessions[i] = s
                    break

            data["sessions"] = sessions
            await self._save_data(data)

    async def list_sessions(self) -> List[Dict]:
        """列出所有会话（摘要信息）"""
        data = await self._load_data()
        sessions = data.get("sessions", [])
        result = []
        for s in sessions:
            result.append(
                {
                    "id": s.get("id", ""),
                    "title": s.get("title", ""),
                    "message_count": len(s.get("messages", [])),
                    "created_at": s.get("created_at", 0),
                    "updated_at": s.get("updated_at", 0),
                }
            )
        # 按更新时间倒序
        result.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return result

    async def delete_session(self, session_id: str) -> bool:
        """删除指定会话"""
        storage = get_storage()
        async with storage.acquire_lock("copilot_data", timeout=5):
            data = await self._load_data()
            sessions = data.get("sessions", [])
            original_len = len(sessions)
            sessions = [s for s in sessions if s.get("id") != session_id]

            if len(sessions) == original_len:
                return False

            data["sessions"] = sessions
            await self._save_data(data)
            logger.info(f"CopilotMemory: 删除会话 {session_id}")
            return True

    async def get_history_messages(self, session_id: str) -> List[Dict]:
        """
        获取裁剪后的历史消息（OpenAI messages 格式）

        按 max_history_turns 限制返回最近的消息
        """
        session = await self.get_session(session_id)
        if not session:
            return []

        max_turns = get_config("copilot.max_history_turns", 20)
        messages = session.messages

        # 每轮 = 一条 user + 一条 assistant，取最近 N 轮
        if len(messages) > max_turns * 2:
            messages = messages[-(max_turns * 2) :]

        # 转换为 OpenAI 格式
        result = []
        for msg in messages:
            result.append({"role": msg.role, "content": msg.content})
        return result
