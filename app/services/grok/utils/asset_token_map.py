"""
Asset-Token 映射

将视频/图片资产 ID 与生成时使用的 token 绑定，
以便视频延长时自动使用同一 token。
"""

import time
from typing import Optional

from app.core.logger import logger

# 默认 TTL: 30 分钟
DEFAULT_TTL = 1800


class AssetTokenMap:
    """内存缓存：asset_id -> token 映射"""

    _instance: Optional["AssetTokenMap"] = None

    def __init__(self, ttl: int = DEFAULT_TTL):
        self._store: dict[str, tuple[str, float]] = {}
        self._ttl = ttl

    @classmethod
    def get_instance(cls) -> "AssetTokenMap":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _cleanup(self) -> None:
        """清理过期条目"""
        now = time.time()
        expired = [k for k, (_, ts) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            del self._store[k]

    def save_mapping(self, asset_id: str, token: str) -> None:
        """保存 asset_id -> token 映射"""
        if not asset_id or not token:
            return
        self._cleanup()
        self._store[asset_id] = (token, time.time())
        logger.debug(f"AssetTokenMap: saved {asset_id[:12]}... -> token={token[:10]}...")

    def get_token(self, asset_id: str) -> Optional[str]:
        """获取 asset_id 绑定的 token"""
        if not asset_id:
            return None
        entry = self._store.get(asset_id)
        if entry is None:
            return None
        token, ts = entry
        if time.time() - ts > self._ttl:
            del self._store[asset_id]
            return None
        return token

    def remove(self, asset_id: str) -> None:
        """移除映射"""
        self._store.pop(asset_id, None)

    def clear(self) -> None:
        """清空所有映射"""
        self._store.clear()


__all__ = ["AssetTokenMap"]
