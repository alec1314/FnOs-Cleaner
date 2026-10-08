"""媒体缓存扫描器：缩略图、播放缓存"""
import os
import time
from .base import BaseScanner


class MediaCacheScanner(BaseScanner):
    module_name = "media_cache"

    def scan(self) -> list[dict]:
        keep_days = self.config.get("keep_days", 30)
        cutoff = time.time() - keep_days * 86400

        for cache_dir in self.config.get("cache_paths", []):
            if not os.path.isdir(cache_dir):
                continue
            for root, _dirs, files in os.walk(cache_dir):
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
                        "item_type": "cache_file",
                        "item_name": f,
                        "size_bytes": os.path.getsize(path),
                        "path": path,
                        "description": f"媒体缓存，生成于 {time.ctime(mtime)}",
                    })
        return self.items
