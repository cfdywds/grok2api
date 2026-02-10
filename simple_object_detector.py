"""
简单的物体检测器

只判断图片是否有明确的物体/内容
使用边缘检测和内容分析
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any


class SimpleObjectDetector:
    """
    简单的物体检测器

    判断图片是否有明确的物体/内容
    - 有物体：边缘清晰，内容丰富
    - 无物体：模糊、空白、纯色
    """

    def __init__(self):
        """初始化检测器"""
        # 边缘密度阈值（物体应该有足够的边缘）
        self.edge_threshold = 0.02  # 2%的像素应该是边缘

        # 内容方差阈值（物体应该有足够的内容变化）
        self.variance_threshold = 100

        # 综合判断阈值
        self.quality_threshold = 40

    def detect(self, image_path: str) -> Dict[str, Any]:
        """
        检测图片是否有明确的物体

        Args:
            image_path: 图片路径

        Returns:
            检测结果字典
        """
        try:
            # 读取图片
            image = cv2.imread(str(image_path))
            if image is None:
                return {
                    "success": False,
                    "error": "无法读取图片"
                }

            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 1. 边缘检测（检测物体轮廓）
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size
            edge_score = min(100, (edge_density / self.edge_threshold) * 100)

            # 2. 内容方差（检测内容丰富度）
            variance = gray.var()
            variance_score = min(100, (variance / self.variance_threshold) * 100)

            # 3. Laplacian 方差（检测清晰度）
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            sharpness_score = min(100, (laplacian_var / 100) * 100)

            # 综合评分（边缘40% + 内容30% + 清晰度30%）
            quality_score = (
                edge_score * 0.4 +
                variance_score * 0.3 +
                sharpness_score * 0.3
            )

            # 判断是否有明确的物体
            has_object = quality_score >= self.quality_threshold

            # 生成问题描述
            issues = []
            if edge_score < 40:
                issues.append("缺少明确的物体轮廓")
            if variance_score < 40:
                issues.append("内容单调或空白")
            if sharpness_score < 40:
                issues.append("图片模糊")

            # 生成状态描述
            if quality_score >= 80:
                status = "有明确的物体"
            elif quality_score >= 60:
                status = "有物体但不够清晰"
            elif quality_score >= 40:
                status = "物体不明确"
            else:
                status = "无明确物体"

            return {
                "success": True,
                "has_object": has_object,
                "quality_score": round(quality_score, 2),
                "edge_score": round(edge_score, 2),
                "variance_score": round(variance_score, 2),
                "sharpness_score": round(sharpness_score, 2),
                "edge_density": round(edge_density, 4),
                "variance": round(variance, 2),
                "laplacian_variance": round(laplacian_var, 2),
                "status": status,
                "quality_issues": issues,
                # 保持兼容性
                "blur_score": round(sharpness_score, 2),
                "brightness_score": 0,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def batch_detect(self, image_paths: list) -> Dict[str, Any]:
        """
        批量检测图片

        Args:
            image_paths: 图片路径列表

        Returns:
            批量检测结果
        """
        results = []
        has_object_count = 0
        no_object_count = 0

        for path in image_paths:
            result = self.detect(path)
            if result.get("success"):
                if result.get("has_object"):
                    has_object_count += 1
                else:
                    no_object_count += 1
            results.append(result)

        return {
            "total": len(image_paths),
            "has_object_count": has_object_count,
            "no_object_count": no_object_count,
            "results": results
        }


def test_detector():
    """测试检测器"""
    detector = SimpleObjectDetector()

    # 测试单张图片
    test_image = Path("data/tmp/image")
    if test_image.exists():
        images = list(test_image.glob("*.jpg"))[:10]

        print("=" * 60)
        print("物体检测测试")
        print("=" * 60)

        for img in images:
            result = detector.detect(str(img))
            if result["success"]:
                print(f"\n图片: {img.name}")
                print(f"  状态: {result['status']}")
                print(f"  有物体: {'是' if result['has_object'] else '否'}")
                print(f"  质量分数: {result['quality_score']}")
                print(f"  边缘分数: {result['edge_score']}")
                print(f"  内容分数: {result['variance_score']}")
                print(f"  清晰度: {result['sharpness_score']}")
                if result['quality_issues']:
                    print(f"  问题: {', '.join(result['quality_issues'])}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    test_detector()
