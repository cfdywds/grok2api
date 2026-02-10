#!/usr/bin/env python3
"""
重复图片扫描和清理工具

功能：
1. 扫描 data/tmp/image 目录下的所有图片
2. 计算每张图片的 SHA256 哈希值
3. 找出重复的图片
4. 提供清理选项（保留最早的，删除其他）
5. 更新元数据文件
"""

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.core.storage import get_storage
from app.core.logger import logger


class DuplicateImageCleaner:
    """重复图片清理器"""

    def __init__(self, image_dir: Path, dry_run: bool = True):
        """
        初始化清理器

        Args:
            image_dir: 图片目录
            dry_run: 是否为试运行模式（不实际删除文件）
        """
        self.image_dir = image_dir
        self.dry_run = dry_run
        self.storage = get_storage()

    def calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件的 SHA256 哈希值

        Args:
            file_path: 文件路径

        Returns:
            SHA256 哈希值（十六进制字符串）
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # 分块读取，避免大文件占用过多内存
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def scan_images(self) -> Dict[str, List[Tuple[Path, datetime]]]:
        """
        扫描图片目录，按哈希值分组

        Returns:
            字典，key为哈希值，value为文件路径和修改时间的列表
        """
        hash_map: Dict[str, List[Tuple[Path, datetime]]] = {}
        total_files = 0
        processed_files = 0

        print(f"\n[*] 扫描目录: {self.image_dir}")
        print("=" * 80)

        # 获取所有图片文件
        image_files = list(self.image_dir.glob("*.jpg")) + list(self.image_dir.glob("*.png"))
        total_files = len(image_files)

        print(f"[*] 找到 {total_files} 个图片文件\n")

        for file_path in image_files:
            try:
                # 计算哈希值
                file_hash = self.calculate_file_hash(file_path)

                # 获取文件修改时间
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                # 添加到哈希映射
                if file_hash not in hash_map:
                    hash_map[file_hash] = []
                hash_map[file_hash].append((file_path, mtime))

                processed_files += 1

                # 显示进度
                if processed_files % 100 == 0:
                    progress = (processed_files / total_files) * 100
                    print(f"[*] 进度: {processed_files}/{total_files} ({progress:.1f}%)")

            except Exception as e:
                logger.error(f"处理文件失败 {file_path}: {e}")
                continue

        print(f"[+] 扫描完成: {processed_files}/{total_files} 个文件")
        return hash_map

    def find_duplicates(self, hash_map: Dict[str, List[Tuple[Path, datetime]]]) -> Dict[str, List[Tuple[Path, datetime]]]:
        """
        从哈希映射中找出重复的图片

        Args:
            hash_map: 哈希值到文件列表的映射

        Returns:
            只包含重复图片的哈希映射
        """
        duplicates = {
            hash_val: files
            for hash_val, files in hash_map.items()
            if len(files) > 1
        }
        return duplicates

    async def display_duplicates(self, duplicates: Dict[str, List[Tuple[Path, datetime]]]):
        """
        显示重复图片信息

        Args:
            duplicates: 重复图片的哈希映射
        """
        if not duplicates:
            print("\n[*] 没有发现重复的图片！")
            return

        print(f"\n[!] 发现 {len(duplicates)} 组重复图片")
        print("=" * 80)

        # 加载元数据以检查提示词
        metadata = await self.load_metadata()
        filename_to_metadata = {img["filename"]: img for img in metadata.get("images", [])}

        total_duplicates = sum(len(files) - 1 for files in duplicates.values())
        total_size = 0

        for idx, (hash_val, files) in enumerate(duplicates.items(), 1):
            # 智能排序：优先保留有提示词的，其次按时间
            def sort_key(item):
                file_path, mtime = item
                img_meta = filename_to_metadata.get(file_path.name, {})
                prompt = img_meta.get("prompt", "")
                # 有提示词的排在前面（返回0），没有的排在后面（返回1）
                # 然后按时间排序
                has_prompt = 0 if prompt and prompt.strip() and not prompt.startswith("导入:") else 1
                return (has_prompt, mtime)

            files.sort(key=sort_key)

            print(f"\n[{idx}] 哈希: {hash_val[:16]}... ({len(files)} 个文件)")

            for file_idx, (file_path, mtime) in enumerate(files):
                file_size = file_path.stat().st_size
                size_kb = file_size / 1024

                # 获取提示词信息
                img_meta = filename_to_metadata.get(file_path.name, {})
                prompt = img_meta.get("prompt", "")
                has_prompt = prompt and prompt.strip() and not prompt.startswith("导入:")

                if file_idx == 0:
                    status = "[保留]"
                    reason = " (有提示词)" if has_prompt else " (最早)"
                else:
                    status = "[删除]"
                    reason = ""
                    total_size += file_size

                print(f"  {status} {file_path.name}{reason}")
                print(f"         大小: {size_kb:.1f} KB | 时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
                if prompt:
                    prompt_preview = prompt[:60] + "..." if len(prompt) > 60 else prompt
                    print(f"         提示词: {prompt_preview}")

        print("\n" + "=" * 80)
        print(f"[*] 统计:")
        print(f"  - 重复组数: {len(duplicates)}")
        print(f"  - 重复文件数: {total_duplicates}")
        print(f"  - 可释放空间: {total_size / (1024 * 1024):.2f} MB")

    async def load_metadata(self) -> Dict:
        """加载图片元数据"""
        try:
            return await self.storage.load_image_metadata()
        except Exception as e:
            logger.error(f"加载元数据失败: {e}")
            return {"images": []}

    async def save_metadata(self, data: Dict):
        """保存图片元数据"""
        try:
            await self.storage.save_image_metadata(data)
        except Exception as e:
            logger.error(f"保存元数据失败: {e}")

    async def cleanup_duplicates(self, duplicates: Dict[str, List[Tuple[Path, datetime]]]):
        """
        清理重复图片

        Args:
            duplicates: 重复图片的哈希映射
        """
        if not duplicates:
            print("\n[*] 没有需要清理的重复图片")
            return

        print(f"\n[*] 开始清理重复图片...")
        print("=" * 80)

        # 加载元数据
        metadata = await self.load_metadata()
        images = metadata.get("images", [])

        # 创建文件名到元数据的映射
        filename_to_metadata = {img["filename"]: img for img in images}

        deleted_files = 0
        deleted_size = 0
        deleted_metadata_ids = set()
        kept_files = set()

        for hash_val, files in duplicates.items():
            # 智能排序：优先保留有提示词的，其次按时间
            def sort_key(item):
                file_path, mtime = item
                img_meta = filename_to_metadata.get(file_path.name, {})
                prompt = img_meta.get("prompt", "")
                # 有提示词的排在前面（返回0），没有的排在后面（返回1）
                has_prompt = 0 if prompt and prompt.strip() and not prompt.startswith("导入:") else 1
                return (has_prompt, mtime)

            files.sort(key=sort_key)

            # 保留第一个（有提示词或最早的），删除其他
            keep_file = files[0][0]
            kept_files.add(keep_file.name)

            # 确保保留的文件在元数据中有 content_hash
            if keep_file.name in filename_to_metadata:
                keep_metadata = filename_to_metadata[keep_file.name]
                if "metadata" not in keep_metadata:
                    keep_metadata["metadata"] = {}
                if "content_hash" not in keep_metadata["metadata"]:
                    keep_metadata["metadata"]["content_hash"] = hash_val
                    print(f"  [*] 更新元数据: {keep_file.name} (添加哈希值)")

            for file_path, mtime in files[1:]:
                file_size = file_path.stat().st_size

                if self.dry_run:
                    print(f"  [-] [试运行] 将删除: {file_path.name} ({file_size / 1024:.1f} KB)")
                else:
                    try:
                        # 删除文件
                        file_path.unlink()
                        print(f"  [+] 已删除: {file_path.name} ({file_size / 1024:.1f} KB)")

                        # 记录需要从元数据中删除的文件
                        if file_path.name in filename_to_metadata:
                            img_id = filename_to_metadata[file_path.name]["id"]
                            deleted_metadata_ids.add(img_id)

                        deleted_files += 1
                        deleted_size += file_size

                    except Exception as e:
                        logger.error(f"删除文件失败 {file_path}: {e}")

        # 更新元数据
        if not self.dry_run and deleted_metadata_ids:
            print(f"\n[*] 更新元数据...")

            # 过滤掉已删除的图片
            updated_images = [
                img for img in images
                if img["id"] not in deleted_metadata_ids
            ]

            metadata["images"] = updated_images
            await self.save_metadata(metadata)

            print(f"  [+] 已从元数据中移除 {len(deleted_metadata_ids)} 条记录")

        print("\n" + "=" * 80)
        if self.dry_run:
            print(f"[*] 试运行模式 - 未实际删除文件")
            print(f"  - 将删除文件数: {sum(len(files) - 1 for files in duplicates.values())}")
            print(f"  - 将释放空间: {sum(f[0].stat().st_size for files in duplicates.values() for f in files[1:]) / (1024 * 1024):.2f} MB")
        else:
            print(f"[+] 清理完成")
            print(f"  - 已删除文件数: {deleted_files}")
            print(f"  - 已释放空间: {deleted_size / (1024 * 1024):.2f} MB")
            print(f"  - 已更新元数据: {len(deleted_metadata_ids)} 条")

    async def add_missing_hashes(self):
        """为现有图片添加缺失的哈希值"""
        print(f"\n[*] 检查并添加缺失的哈希值...")
        print("=" * 80)

        # 加载元数据
        metadata = await self.load_metadata()
        images = metadata.get("images", [])

        updated_count = 0

        for img in images:
            filename = img.get("filename")
            if not filename:
                continue

            file_path = self.image_dir / filename
            if not file_path.exists():
                continue

            # 检查是否已有哈希值
            img_metadata = img.get("metadata", {})
            if "content_hash" in img_metadata:
                continue

            # 计算哈希值
            try:
                content_hash = self.calculate_file_hash(file_path)

                # 更新元数据
                if "metadata" not in img:
                    img["metadata"] = {}
                img["metadata"]["content_hash"] = content_hash

                updated_count += 1

                if updated_count % 100 == 0:
                    print(f"  [*] 已更新 {updated_count} 个文件...")

            except Exception as e:
                logger.error(f"计算哈希失败 {filename}: {e}")

        if updated_count > 0:
            if not self.dry_run:
                await self.save_metadata(metadata)
                print(f"  [+] 已为 {updated_count} 个文件添加哈希值")
            else:
                print(f"  [*] [试运行] 将为 {updated_count} 个文件添加哈希值")
        else:
            print(f"  [*] 所有文件都已有哈希值")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="重复图片扫描和清理工具")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="执行清理（默认为试运行模式）"
    )
    parser.add_argument(
        "--add-hashes",
        action="store_true",
        help="为现有图片添加缺失的哈希值"
    )
    parser.add_argument(
        "--image-dir",
        type=str,
        default="data/tmp/image",
        help="图片目录路径（默认: data/tmp/image）"
    )

    args = parser.parse_args()

    # 确定运行模式
    dry_run = not args.clean

    # 初始化清理器
    image_dir = Path(args.image_dir)
    if not image_dir.exists():
        print(f"[!] 错误: 图片目录不存在: {image_dir}")
        return

    cleaner = DuplicateImageCleaner(image_dir, dry_run=dry_run)

    # 添加缺失的哈希值
    if args.add_hashes:
        await cleaner.add_missing_hashes()
        return

    # 扫描图片
    hash_map = cleaner.scan_images()

    # 找出重复的图片
    duplicates = cleaner.find_duplicates(hash_map)

    # 显示重复图片
    await cleaner.display_duplicates(duplicates)

    # 清理重复图片
    if duplicates:
        print("\n" + "=" * 80)
        if dry_run:
            print("[*] 提示: 这是试运行模式，未实际删除文件")
            print("   要执行实际清理，请使用 --clean 参数")
            print("\n[*] 清理策略: 优先保留有提示词的图片，其次保留最早的图片")
        else:
            print("[!] 警告: 即将删除重复文件！")
            print("[*] 清理策略: 优先保留有提示词的图片，其次保留最早的图片")
            response = input("   确认继续？(yes/no): ")
            if response.lower() != "yes":
                print("[!] 已取消清理")
                return

        await cleaner.cleanup_duplicates(duplicates)


if __name__ == "__main__":
    asyncio.run(main())
