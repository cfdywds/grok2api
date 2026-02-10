"""
图片元数据自动备份服务

功能：
1. 在每次修改元数据前自动创建备份
2. 定期自动备份（每小时一次）
3. 保留多个版本的备份（按时间和数量限制）
4. 支持快速恢复到任意备份版本
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncio

from app.core.logger import logger


class MetadataBackupService:
    """元数据备份服务"""

    def __init__(self):
        self.metadata_file = Path(__file__).parent.parent.parent.parent / "data" / "image_metadata.json"
        self.backup_dir = Path(__file__).parent.parent.parent.parent / "data" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # 备份配置
        self.max_backups = 100  # 最多保留 100 个备份
        self.backup_interval_hours = 1  # 每小时自动备份一次
        self.keep_daily_backups_days = 30  # 保留 30 天的每日备份
        self.keep_hourly_backups_hours = 72  # 保留 72 小时的每小时备份

    def create_backup(self, reason: str = "manual") -> Optional[Path]:
        """
        创建备份

        Args:
            reason: 备份原因（manual, auto, before_update, before_scan 等）

        Returns:
            备份文件路径，失败返回 None
        """
        try:
            if not self.metadata_file.exists():
                logger.warning(f"元数据文件不存在，无法备份: {self.metadata_file}")
                return None

            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"image_metadata_{timestamp}_{reason}.json"
            backup_path = self.backup_dir / backup_filename

            # 复制文件
            shutil.copy2(self.metadata_file, backup_path)

            # 记录备份信息
            backup_info = {
                "timestamp": timestamp,
                "reason": reason,
                "file_size": backup_path.stat().st_size,
                "created_at": datetime.now().isoformat(),
            }

            # 保存备份信息
            info_path = backup_path.with_suffix(".json.info")
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(backup_info, f, ensure_ascii=False, indent=2)

            logger.info(f"创建备份成功: {backup_filename} (原因: {reason})")
            return backup_path

        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return None

    def cleanup_old_backups(self):
        """清理旧备份，保留重要的备份"""
        try:
            # 获取所有备份文件
            backups = sorted(self.backup_dir.glob("image_metadata_*.json"))

            if len(backups) <= self.max_backups:
                return

            # 按时间分类备份
            now = datetime.now()
            keep_backups = set()

            for backup_path in backups:
                # 解析时间戳
                try:
                    timestamp_str = backup_path.stem.split('_')[2] + backup_path.stem.split('_')[3]
                    backup_time = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                except Exception:
                    continue

                age_hours = (now - backup_time).total_seconds() / 3600

                # 保留策略：
                # 1. 最近 72 小时：保留所有每小时备份
                # 2. 最近 30 天：保留每日备份（每天保留第一个）
                # 3. 30 天以上：保留每周备份（每周保留第一个）

                if age_hours <= self.keep_hourly_backups_hours:
                    # 保留最近 72 小时的所有备份
                    keep_backups.add(backup_path)
                elif age_hours <= self.keep_daily_backups_days * 24:
                    # 保留每日备份
                    date_key = backup_time.strftime("%Y%m%d")
                    if not any(date_key in str(p) for p in keep_backups):
                        keep_backups.add(backup_path)
                else:
                    # 保留每周备份
                    week_key = backup_time.strftime("%Y%W")
                    if not any(week_key in str(p) for p in keep_backups):
                        keep_backups.add(backup_path)

            # 删除不需要保留的备份
            deleted_count = 0
            for backup_path in backups:
                if backup_path not in keep_backups:
                    try:
                        backup_path.unlink()
                        # 同时删除 .info 文件
                        info_path = backup_path.with_suffix(".json.info")
                        if info_path.exists():
                            info_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"删除备份失败 {backup_path}: {e}")

            if deleted_count > 0:
                logger.info(f"清理旧备份: 删除 {deleted_count} 个，保留 {len(keep_backups)} 个")

        except Exception as e:
            logger.error(f"清理旧备份失败: {e}")

    def list_backups(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        列出所有备份

        Args:
            limit: 最多返回的备份数量

        Returns:
            备份列表
        """
        try:
            backups = []
            backup_files = sorted(
                self.backup_dir.glob("image_metadata_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            for backup_path in backup_files[:limit]:
                # 读取备份信息
                info_path = backup_path.with_suffix(".json.info")
                backup_info = {}

                if info_path.exists():
                    try:
                        with open(info_path, 'r', encoding='utf-8') as f:
                            backup_info = json.load(f)
                    except Exception:
                        pass

                # 基本信息
                stat = backup_path.stat()
                backups.append({
                    "filename": backup_path.name,
                    "path": str(backup_path),
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "reason": backup_info.get("reason", "unknown"),
                    "timestamp": backup_info.get("timestamp", ""),
                })

            return backups

        except Exception as e:
            logger.error(f"列出备份失败: {e}")
            return []

    def restore_backup(self, backup_filename: str) -> bool:
        """
        恢复备份

        Args:
            backup_filename: 备份文件名

        Returns:
            是否恢复成功
        """
        try:
            backup_path = self.backup_dir / backup_filename

            if not backup_path.exists():
                logger.error(f"备份文件不存在: {backup_filename}")
                return False

            # 在恢复前先备份当前文件
            self.create_backup(reason="before_restore")

            # 恢复备份
            shutil.copy2(backup_path, self.metadata_file)

            logger.info(f"恢复备份成功: {backup_filename}")
            return True

        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False

    async def start_auto_backup(self):
        """启动自动备份任务"""
        logger.info(f"启动自动备份任务，间隔: {self.backup_interval_hours} 小时")

        while True:
            try:
                # 等待指定时间
                await asyncio.sleep(self.backup_interval_hours * 3600)

                # 创建自动备份
                self.create_backup(reason="auto")

                # 清理旧备份
                self.cleanup_old_backups()

            except Exception as e:
                logger.error(f"自动备份任务出错: {e}")
                # 出错后等待 5 分钟再重试
                await asyncio.sleep(300)


# 全局单例
_backup_service: Optional[MetadataBackupService] = None


def get_backup_service() -> MetadataBackupService:
    """获取备份服务单例"""
    global _backup_service
    if _backup_service is None:
        _backup_service = MetadataBackupService()
    return _backup_service


__all__ = ["MetadataBackupService", "get_backup_service"]
