"""
二维码生成 API
"""
import socket
import qrcode
from io import BytesIO
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.core.logger import logger

router = APIRouter(prefix="/api/v1/qrcode", tags=["QRCode"])


def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        # 创建一个UDP socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 连接到一个外部地址（不需要真的连接）
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"获取本机IP失败: {e}")
        return "127.0.0.1"


@router.get("/generate")
async def generate_qrcode(
    url: str = None,
    port: int = 8000,
    path: str = ""
):
    """
    生成二维码
    
    Args:
        url: 完整URL（如果提供则直接使用）
        port: 端口号（默认8000）
        path: 路径（默认为空）
    
    Returns:
        二维码图片
    """
    try:
        # 如果没有提供完整URL，则自动生成
        if not url:
            local_ip = get_local_ip()
            url = f"http://{local_ip}:{port}{path}"
        
        logger.info(f"生成二维码: {url}")
        
        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # 创建图片
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 保存到内存
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        
        return StreamingResponse(buf, media_type="image/png")
        
    except Exception as e:
        logger.error(f"生成二维码失败: {e}")
        raise


@router.get("/info")
async def get_qrcode_info(port: int = 8000):
    """
    获取二维码信息（IP地址等）
    
    Args:
        port: 端口号（默认8000）
    
    Returns:
        包含IP地址和URL的信息
    """
    try:
        local_ip = get_local_ip()
        url = f"http://{local_ip}:{port}"
        
        return {
            "success": True,
            "data": {
                "local_ip": local_ip,
                "port": port,
                "url": url,
                "qrcode_url": f"/api/v1/qrcode/generate?port={port}"
            }
        }
        
    except Exception as e:
        logger.error(f"获取二维码信息失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }
