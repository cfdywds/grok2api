"""
图片 EXIF 元数据管理工具

功能：
1. 将提示词等信息写入图片的 EXIF 数据
2. 从图片的 EXIF 数据中读取提示词
3. 确保图片和提示词永远绑定在一起
"""

from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
from PIL.ExifTags import TAGS
import piexif
import json

from app.core.logger import logger


class ImageExifManager:
    """图片 EXIF 元数据管理器"""

    # EXIF 标签定义
    EXIF_TAG_USER_COMMENT = 0x9286  # UserComment - 用于存储 JSON 格式的元数据
    EXIF_TAG_IMAGE_DESCRIPTION = 0x010E  # ImageDescription - 用于存储提示词

    def write_metadata_to_image(
        self,
        image_path: Path,
        prompt: str,
        model: str = "grok-imagine-1.0",
        aspect_ratio: str = "1:1",
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        将元数据写入图片的 EXIF 数据

        Args:
            image_path: 图片文件路径
            prompt: 生成提示词
            model: 使用的模型
            aspect_ratio: 宽高比
            additional_metadata: 额外的元数据

        Returns:
            是否写入成功
        """
        try:
            if not image_path.exists():
                logger.error(f"图片文件不存在: {image_path}")
                return False

            # 读取图片
            img = Image.open(image_path)

            # 准备元数据
            metadata = {
                "prompt": prompt,
                "model": model,
                "aspect_ratio": aspect_ratio,
            }

            if additional_metadata:
                metadata.update(additional_metadata)

            # 将元数据转换为 JSON 字符串
            metadata_json = json.dumps(metadata, ensure_ascii=False)

            # 读取现有的 EXIF 数据（如果有）
            try:
                exif_dict = piexif.load(image_path)
            except Exception:
                # 如果没有 EXIF 数据，创建新的
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

            # 写入提示词到 ImageDescription（方便查看）
            exif_dict["0th"][self.EXIF_TAG_IMAGE_DESCRIPTION] = prompt.encode('utf-8')

            # 写入完整元数据到 UserComment（JSON 格式）
            exif_dict["Exif"][self.EXIF_TAG_USER_COMMENT] = metadata_json.encode('utf-8')

            # 转换为字节
            exif_bytes = piexif.dump(exif_dict)

            # 保存图片（带 EXIF 数据）
            img.save(image_path, exif=exif_bytes, quality=95)

            logger.info(f"成功将元数据写入图片: {image_path.name}")
            return True

        except Exception as e:
            logger.error(f"写入图片元数据失败 {image_path}: {e}")
            return False

    def read_metadata_from_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """
        从图片的 EXIF 数据中读取元数据

        Args:
            image_path: 图片文件路径

        Returns:
            元数据字典，失败返回 None
        """
        try:
            if not image_path.exists():
                logger.error(f"图片文件不存在: {image_path}")
                return None

            # 读取 EXIF 数据
            exif_dict = piexif.load(str(image_path))

            # 尝试从 UserComment 读取完整元数据（JSON 格式）
            if "Exif" in exif_dict and self.EXIF_TAG_USER_COMMENT in exif_dict["Exif"]:
                try:
                    user_comment = exif_dict["Exif"][self.EXIF_TAG_USER_COMMENT]
                    # 解码字节
                    if isinstance(user_comment, bytes):
                        metadata_json = user_comment.decode('utf-8')
                        metadata = json.loads(metadata_json)
                        logger.debug(f"从 EXIF 读取到完整元数据: {image_path.name}")
                        return metadata
                except Exception as e:
                    logger.debug(f"解析 UserComment 失败: {e}")

            # 如果 UserComment 读取失败，尝试从 ImageDescription 读取提示词
            if "0th" in exif_dict and self.EXIF_TAG_IMAGE_DESCRIPTION in exif_dict["0th"]:
                try:
                    description = exif_dict["0th"][self.EXIF_TAG_IMAGE_DESCRIPTION]
                    if isinstance(description, bytes):
                        prompt = description.decode('utf-8')
                        logger.debug(f"从 EXIF 读取到提示词: {image_path.name}")
                        return {
                            "prompt": prompt,
                            "model": "unknown",
                            "aspect_ratio": "unknown"
                        }
                except Exception as e:
                    logger.debug(f"解析 ImageDescription 失败: {e}")

            logger.debug(f"图片中没有找到元数据: {image_path.name}")
            return None

        except Exception as e:
            logger.debug(f"读取图片元数据失败 {image_path}: {e}")
            return None

    def has_metadata(self, image_path: Path) -> bool:
        """
        检查图片是否包含元数据

        Args:
            image_path: 图片文件路径

        Returns:
            是否包含元数据
        """
        metadata = self.read_metadata_from_image(image_path)
        return metadata is not None and "prompt" in metadata


# 全局单例
_exif_manager: Optional[ImageExifManager] = None


def get_exif_manager() -> ImageExifManager:
    """获取 EXIF 管理器单例"""
    global _exif_manager
    if _exif_manager is None:
        _exif_manager = ImageExifManager()
    return _exif_manager


__all__ = ["ImageExifManager", "get_exif_manager"]
