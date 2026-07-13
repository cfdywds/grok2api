"""
Copilot 服务默认配置
"""

COPILOT_DEFAULTS = {
    "copilot": {
        # 是否启用 Copilot 功能
        "enabled": True,
        # LM Studio 连接配置
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "",
        "lmstudio_timeout": 60,
        # 会话记忆配置
        "max_history_turns": 20,
        # 图片生成配置
        "image_model": "grok-imagine-1.0",
        "image_n": 1,
        "image_aspect_ratio": "1:1",
        "image_min_bytes": 50000,
        "image_max_attempts": 10,
    },
}


def get_copilot_defaults():
    """获取 Copilot 默认配置"""
    return COPILOT_DEFAULTS


__all__ = ["COPILOT_DEFAULTS", "get_copilot_defaults"]
