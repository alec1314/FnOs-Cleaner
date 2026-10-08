"""下载工具残留扫描器：未完成下载、临时文件、残留种子"""
import glob
import os
import time
from .base import BaseScanner


class DownloadResidueScanner(BaseScanner):
    module_name = "download_residue"

    def scan(self) -> list[dict]:
        keep_days = self.config.get("keep_days", 3)
        cutoff = time.time() - keep_days * 86400
        patterns = self.config.get("temp_patterns", [])
        scan_paths = self.config.get("scan_paths", [])

        for base in scan_paths:
            if not os.path.isdir(base):
                continue
            for pat in patterns:
                full_pattern = os.path.join(base, pat)
                for path in glob.glob(full_pattern, recursive=True):
                    if not os.path.isfile(path):
                        continue
                    mtime = os.path.getmtime(path)
                    if mtime > cutoff:
                        continue
                    size = os.path.getsize(path)
                    self.items.append({
                        "module": self.module_name,
                        "item_type": "file",
                        "item_name": os.path.basename(path),
                        "size_bytes": size,
                        "path": path,
                        "description": f"临时下载残留，修改于 {time.ctime(mtime)}",
                    })
        return self.items
