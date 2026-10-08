"""扫描器基类"""
from abc import ABC, abstractmethod


class BaseScanner(ABC):
    """所有扫描模块的基类"""
    module_name = "base"

    def __init__(self, config: dict):
        self.config = config or {}
        self.items: list[dict] = []

    @abstractmethod
    def scan(self) -> list[dict]:
        """
        扫描并返回可清理项列表。
        每项格式：
        {
            "module": str,
            "item_type": str,   # container/image/volume/file/...
            "item_name": str,   # 显示名称
            "size_bytes": int,
            "path": str,        # 文件路径或资源标识
            "description": str,
        }
        """
        ...

    def enabled(self) -> bool:
        return self.config.get("enabled", False)
