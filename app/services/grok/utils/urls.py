"""
Grok URL 构建工具

根据 network.grok_base_url 配置动态构建 API 地址，
支持通过 Cloudflare Workers 反代绕过 CF 挑战。
"""

from typing import Dict

from app.core.config import get_config

_DEFAULT_BASE = "https://grok.com"


def grok_url(path: str) -> str:
    """构建 Grok HTTP API URL

    Args:
        path: API 路径，如 /rest/app-chat/conversations/new

    Returns:
        完整 URL，优先使用 grok_base_url 配置，为空时回退到 https://grok.com
    """
    base = get_config("network.grok_base_url") or _DEFAULT_BASE
    return f"{base.rstrip('/')}{path}"


def grok_ws_url(path: str) -> str:
    """构建 Grok WebSocket URL

    Args:
        path: WebSocket 路径，如 /ws/imagine/listen

    Returns:
        完整 WebSocket URL，自动将 https:// 替换为 wss://
    """
    base = get_config("network.grok_base_url") or _DEFAULT_BASE
    base = base.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    return f"{base}{path}"


def apply_proxy_token(headers: Dict[str, str]) -> None:
    """如果配置了 CF Worker 鉴权 token，自动注入 X-Proxy-Token 头。

    仅在 grok_base_url 有值时生效（即走反代时才注入）。
    """
    if not get_config("network.grok_base_url"):
        return
    token = get_config("network.grok_proxy_token")
    if token:
        headers["X-Proxy-Token"] = token
