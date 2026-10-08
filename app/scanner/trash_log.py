"""回收站 + 日志扫描器"""
import glob
import os
import time
from .base import BaseScanner


class TrashLogScanner(BaseScanner):
    module_name = "trash_log"

    def scan(self) -> list[dict]:
        keep_days = self.config.get("keep_days", 14)
        cutoff = time.time() - keep_days * 86400

        # 回收站：整个目录下的旧文件
        for trash_dir in self.config.get("trash_paths", []):
            if not os.path.isdir(trash_dir):
                continue
            for root, _dirs, files in os.walk(trash_dir):
                for f in files:
                    path = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    if mtime > cutoff:
                        continue
                    self.items.append({
                        "module": self.module_name,
                        "item_type": "trash_file",
                        "item_name": f,
                        "size_bytes": os.path.getsize(path),
                        "path": path,
                        "description": f"回收站文件，删除于 {time.ctime(mtime)}",
                    })

        # 旧日志
        patterns = self.config.get("log_patterns", [])
        for base in self.config.get("log_paths", []):
            if not os.path.isdir(base):
                continue
            for pat in patterns:
                for path in glob.glob(os.path.join(base, pat), recursive=True):
                    if not os.path.isfile(path):
                        continue
                    mtime = os.path.getmtime(path)
                    if mtime > cutoff:
                        continue
                    self.items.append({
                        "module": self.module_name,
                        "item_type": "log_file",
                        "item_name": os.path.basename(path),
                        "size_bytes": os.path.getsize(path),
                        "path": path,
                        "description": f"旧日志，修改于 {time.ctime(mtime)}",
                    })
        return self.items
