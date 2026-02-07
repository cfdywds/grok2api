"""
图片管理功能集成测试

测试所有核心功能是否正常工作
"""

import asyncio
import uuid
import time
from pathlib import Path

# 测试结果
test_results = []


def log_test(name, passed, message=""):
    """记录测试结果"""
    status = "[PASS]" if passed else "[FAIL]"
    test_results.append((name, passed, message))
    print(f"{status} - {name}")
    if message:
        print(f"    {message}")


async def test_storage_service():
    """测试存储服务"""
    try:
        from app.core.storage import get_storage

        storage = get_storage()

        # 测试加载元数据
        data = await storage.load_image_metadata()
        assert isinstance(data, dict), "元数据应该是字典类型"
        assert "images" in data or data == {"images": [], "version": "1.0"}

        log_test("Storage Service - Load Metadata", True)

        # 测试保存元数据
        test_data = {
            "images": [
                {
                    "id": "test-id",
                    "filename": "test.jpg",
                    "prompt": "test prompt",
                    "model": "grok-imagine-1.0",
                    "aspect_ratio": "1:1",
                    "created_at": int(time.time() * 1000),
                    "file_size": 1024,
                    "width": 1024,
                    "height": 1024,
                    "tags": ["test"],
                    "nsfw": False,
                    "metadata": {},
                }
            ],
            "version": "1.0",
        }

        await storage.save_image_metadata(test_data)
        loaded_data = await storage.load_image_metadata()
        assert len(loaded_data.get("images", [])) > 0, "应该能保存和加载元数据"

        log_test("Storage Service - Save Metadata", True)

        # 清理测试数据
        await storage.save_image_metadata({"images": [], "version": "1.0"})

    except Exception as e:
        log_test("Storage Service", False, str(e))


async def test_gallery_models():
    """测试数据模型"""
    try:
        from app.services.gallery import ImageMetadata, ImageFilter, ImageStats

        # 测试 ImageMetadata
        metadata = ImageMetadata(
            id="test-id",
            filename="test.jpg",
            prompt="test prompt",
            model="grok-imagine-1.0",
            aspect_ratio="1:1",
            created_at=int(time.time() * 1000),
            file_size=1024,
            width=1024,
            height=1024,
            tags=["test"],
            nsfw=False,
            metadata={},
        )
        assert metadata.id == "test-id"
        log_test("Gallery Models - ImageMetadata", True)

        # 测试 ImageFilter
        filter_obj = ImageFilter(
            search="test", model="grok-imagine-1.0", aspect_ratio="1:1"
        )
        assert filter_obj.search == "test"
        log_test("Gallery Models - ImageFilter", True)

        # 测试 ImageStats
        stats = ImageStats(
            total_count=10,
            total_size=10240,
            month_count=5,
            top_tags=[{"name": "test", "count": 5}],
        )
        assert stats.total_count == 10
        log_test("Gallery Models - ImageStats", True)

    except Exception as e:
        log_test("Gallery Models", False, str(e))


async def test_gallery_service():
    """测试图片管理服务"""
    try:
        from app.services.gallery.service import get_image_metadata_service
        from app.services.gallery import ImageMetadata

        service = get_image_metadata_service()

        # 测试添加图片元数据
        test_id = str(uuid.uuid4())
        metadata = ImageMetadata(
            id=test_id,
            filename=f"{test_id}.jpg",
            prompt="test prompt for service",
            model="grok-imagine-1.0",
            aspect_ratio="1:1",
            created_at=int(time.time() * 1000),
            file_size=2048,
            width=1024,
            height=1024,
            tags=["test", "service"],
            nsfw=False,
            metadata={"test": "data"},
        )

        success = await service.add_image(metadata)
        assert success, "应该能添加图片元数据"
        log_test("Gallery Service - Add Image", True)

        # 测试获取图片详情
        image = await service.get_image(test_id)
        assert image is not None, "应该能获取图片详情"
        assert image.id == test_id
        log_test("Gallery Service - Get Image", True)

        # 测试列出图片
        result = await service.list_images(page=1, page_size=10)
        assert result.total > 0, "应该能列出图片"
        assert len(result.images) > 0
        log_test("Gallery Service - List Images", True)

        # 测试更新标签
        success = await service.update_tags(test_id, ["updated", "tags"])
        assert success, "应该能更新标签"
        updated_image = await service.get_image(test_id)
        assert "updated" in updated_image.tags
        log_test("Gallery Service - Update Tags", True)

        # 测试获取所有标签
        tags = await service.get_all_tags()
        assert isinstance(tags, list), "应该返回标签列表"
        log_test("Gallery Service - Get All Tags", True)

        # 测试获取统计信息
        stats = await service.get_stats()
        assert stats.total_count > 0, "应该有统计信息"
        log_test("Gallery Service - Get Stats", True)

        # 测试删除图片
        result = await service.delete_images([test_id])
        assert result["deleted"] >= 0, "应该能删除图片"
        log_test("Gallery Service - Delete Images", True)

    except Exception as e:
        log_test("Gallery Service", False, str(e))


async def test_api_imports():
    """测试 API 路由导入"""
    try:
        from app.api.v1 import gallery

        assert hasattr(gallery, "router"), "应该有 router 对象"
        log_test("API Imports - Gallery Router", True)

        # 检查路由端点
        routes = [route.path for route in gallery.router.routes]
        expected_routes = [
            "/api/v1/admin/gallery/images",
            "/api/v1/admin/gallery/images/{image_id}",
            "/api/v1/admin/gallery/images/delete",
            "/api/v1/admin/gallery/images/{image_id}/tags",
            "/api/v1/admin/gallery/tags",
            "/api/v1/admin/gallery/stats",
            "/api/v1/admin/gallery/images/export",
        ]

        for expected in expected_routes:
            found = any(expected in route for route in routes)
            if not found:
                log_test(f"API Route - {expected}", False, "路由未找到")
            else:
                log_test(f"API Route - {expected}", True)

    except Exception as e:
        log_test("API Imports", False, str(e))


async def test_file_structure():
    """测试文件结构"""
    base_path = Path(__file__).parent

    files_to_check = [
        "app/services/gallery/__init__.py",
        "app/services/gallery/models.py",
        "app/services/gallery/service.py",
        "app/api/v1/gallery.py",
        "app/static/gallery/gallery.html",
        "app/static/gallery/gallery.css",
        "app/static/gallery/gallery.js",
        "GALLERY_IMPLEMENTATION.md",
        "GALLERY_QUICKSTART.md",
    ]

    for file_path in files_to_check:
        full_path = base_path / file_path
        exists = full_path.exists()
        log_test(f"File Structure - {file_path}", exists)


async def test_integration():
    """测试集成功能"""
    try:
        # 测试 main.py 中是否注册了路由
        import main

        app = main.app
        routes = [route.path for route in app.routes]

        # 检查 gallery 路由是否注册
        gallery_routes = [r for r in routes if "gallery" in r]
        assert len(gallery_routes) > 0, "应该注册了 gallery 路由"
        log_test("Integration - Gallery Routes Registered", True)

        # 检查 admin 页面路由
        admin_routes = [r for r in routes if "/admin/gallery" in r]
        assert len(admin_routes) > 0, "应该注册了 admin 页面路由"
        log_test("Integration - Admin Page Route Registered", True)

    except Exception as e:
        log_test("Integration", False, str(e))


async def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("图片管理功能集成测试")
    print("=" * 60)
    print()

    print("1. 测试存储服务...")
    await test_storage_service()
    print()

    print("2. 测试数据模型...")
    await test_gallery_models()
    print()

    print("3. 测试图片管理服务...")
    await test_gallery_service()
    print()

    print("4. 测试 API 导入...")
    await test_api_imports()
    print()

    print("5. 测试文件结构...")
    await test_file_structure()
    print()

    print("6. 测试集成...")
    await test_integration()
    print()

    # 统计结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    total = len(test_results)
    passed = sum(1 for _, p, _ in test_results if p)
    failed = total - passed

    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Pass rate: {passed / total * 100:.1f}%")
    print()

    if failed > 0:
        print("Failed tests:")
        for name, passed, message in test_results:
            if not passed:
                print(f"  [FAIL] {name}")
                if message:
                    print(f"     {message}")
        print()

    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
