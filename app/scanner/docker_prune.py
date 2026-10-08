"""
Docker 资源扫描器（安全版）
============================
安全原则：
- 运行中的容器/镜像/卷/网络：绝对不碰
- 停止的容器：只报告，不自动删（用户可能故意停着备用）
- 悬空卷：只报告，不自动删（卷里可能有想保留的数据）
- 悬空镜像（<none>:<none>）：可安全清理
- 无用网络（非 bridge/host/none）：可安全清理
"""
import docker
from .base import BaseScanner


class DockerPruneScanner(BaseScanner):
    module_name = "docker_prune"

    def __init__(self, config: dict):
        super().__init__(config)
        try:
            self.client = docker.from_env()
            self.available = True
        except Exception:
            self.client = None
            self.available = False

    def scan(self) -> list[dict]:
        if not self.available:
            return []

        # 停止的容器：只报告
        if self.config.get("report_stopped_containers", True):
            self._scan_stopped_containers()
        # 悬空镜像：可安全清理
        if self.config.get("clean_dangling_images", True):
            self._scan_dangling_images()
        # 悬空卷：只报告
        if self.config.get("report_dangling_volumes", True):
            self._scan_dangling_volumes()
        # 无用网络：可安全清理
        if self.config.get("clean_unused_networks", True):
            self._scan_unused_networks()
        return self.items

    def _scan_stopped_containers(self):
        for c in self.client.containers.list(all=True):
            if c.status == "running":
                continue  # 运行中的绝对跳过
            self.items.append({
                "module": self.module_name,
                "item_type": "container",
                "item_name": c.name,
                "size_bytes": int(c.attrs.get("SizeRw", 0) or 0),
                "path": c.id,
                "description": f"状态: {c.status}（停止的容器，需确认后再删）",
            })

    def _scan_dangling_images(self):
        images = self.client.images.list(filters={"dangling": True})
        for img in images:
            self.items.append({
                "module": self.module_name,
                "item_type": "image",
                "item_name": img.short_id,
                "size_bytes": int(img.attrs.get("Size", 0)),
                "path": img.id,
                "description": "悬空镜像（<none>:<none>，无标签无引用）",
            })

    def _scan_dangling_volumes(self):
        volumes = self.client.volumes.list(filters={"dangling": True})
        for v in volumes:
            self.items.append({
                "module": self.module_name,
                "item_type": "volume",
                "item_name": v.name,
                "size_bytes": 0,
                "path": v.attrs.get("Mountpoint", ""),
                "description": "悬空数据卷（无容器引用——但卷里可能有数据，需确认）",
            })

    def _scan_unused_networks(self):
        used = set()
        for c in self.client.containers.list():
            for net in c.attrs.get("NetworkSettings", {}).get("Networks", {}):
                used.add(net)
        for net in self.client.networks.list():
            if net.name not in used and net.name not in ("bridge", "host", "none"):
                self.items.append({
                    "module": self.module_name,
                    "item_type": "network",
                    "item_name": net.name,
                    "size_bytes": 0,
                    "path": net.id,
                    "description": "未被容器使用的自定义网络",
                })
