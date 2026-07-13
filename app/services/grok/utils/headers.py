"""
Common header helpers for Grok services.
"""

from __future__ import annotations

import uuid
from typing import Dict

from app.core.config import get_config
from app.core.logger import logger
from app.services.grok.utils.statsig import StatsigService
from app.services.grok.utils.urls import apply_proxy_token


def _normalize_token(token: str) -> str:
    return token[4:] if token.startswith("sso=") else token


def build_sso_cookie(token: str, include_rw: bool = False) -> str:
    token = _normalize_token(token)
    cf = get_config("security.cf_clearance")
    cookie = f"sso={token}"
    if include_rw:
        cookie = f"{cookie}; sso-rw={token}"
    if cf:
        cookie = f"{cookie};cf_clearance={cf}"
    return cookie


def apply_statsig(headers: Dict[str, str]) -> None:
    headers["x-statsig-id"] = StatsigService.gen_id()
    headers["x-xai-request-id"] = str(uuid.uuid4())


def _sanitize_header_value(name: str, value: str) -> str:
    """Ensure header values are latin-1 encodable for HTTP clients."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    try:
        value.encode("latin-1")
        return value
    except UnicodeEncodeError:
        sanitized = value.encode("latin-1", errors="replace").decode("latin-1")
        logger.warning(f"Sanitized non-latin1 header value: {name}")
        return sanitized


def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Return a copy of headers with latin-1 safe values."""
    return {
        str(name): _sanitize_header_value(str(name), value)
        for name, value in headers.items()
    }


def _build_browser_headers(
    *, referer: str, sec_fetch_mode: str, sec_fetch_dest: str, content_type: str = ""
) -> Dict[str, str]:
    user_agent = get_config("security.user_agent")
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Baggage": "sentry-environment=production,sentry-release=d6add6fb0460641fd482d767a335ef72b9b6abb8,sentry-public_key=b311e0f2690c81f25e2c4cf6d4f7ce1c",
        "Cache-Control": "no-cache",
        "Origin": "https://grok.com",
        "Pragma": "no-cache",
        "Priority": "u=1, i",
        "Referer": referer,
        "Sec-Ch-Ua": '"Google Chrome";v="136", "Chromium";v="136", "Not(A:Brand";v="24"',
        "Sec-Ch-Ua-Arch": "arm",
        "Sec-Ch-Ua-Bitness": "64",
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Model": "",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": sec_fetch_dest,
        "Sec-Fetch-Mode": sec_fetch_mode,
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": user_agent,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def build_grok_headers(token: str, referer: str = "https://grok.com/") -> Dict[str, str]:
    """Build full browser-like headers for Grok HTTP API requests."""
    headers = _build_browser_headers(
        referer=referer,
        sec_fetch_mode="cors",
        sec_fetch_dest="empty",
        content_type="application/json",
    )

    apply_statsig(headers)
    headers["Cookie"] = build_sso_cookie(token)
    apply_proxy_token(headers)

    return sanitize_headers(headers)


def build_grok_ws_headers(
    token: str, referer: str = "https://grok.com/imagine"
) -> Dict[str, str]:
    """Build browser-like headers for Grok WebSocket requests."""
    headers = _build_browser_headers(
        referer=referer,
        sec_fetch_mode="websocket",
        sec_fetch_dest="empty",
    )

    apply_statsig(headers)
    headers["Cookie"] = build_sso_cookie(token, include_rw=True)
    apply_proxy_token(headers)

    return sanitize_headers(headers)
