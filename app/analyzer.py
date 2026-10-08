"""
综合分析器
==========
两部分结合：
1. 固定基线：fnOS 标准目录地图（filesystem_map.py）
2. 动态分析：当前磁盘占用 + Docker 实际运行状态 + 交叉比对

输出：
- 磁盘占用概览（各目录大小）
- Docker 资源清单（容器/镜像/卷，标注使用状态）
- 孤儿目录（目录存在但无对应运行容器）
- 综合可清理项汇总
"""
import os
import docker
from .filesystem_map import (
    BASELINE, classify_path, CATEGORY_PROTECTED, CATEGORY_CLEANABLE,
    CATEGORY_UNKNOWN, FnosPath,
)


def human_size(n: int) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def _dir_size(path: str) -> int:
    """计算目录总大小（字节），出错返回 0"""
    total = 0
    if not os.path.exists(path):
        return 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


# ============================================
# 1. 磁盘占用扫描
# ============================================

def scan_disk_overview() -> list[dict]:
    """
    遍历基线地图中的路径，计算每个目录大小。
    返回按大小排序的列表。
    """
    results = []
    for entry in BASELINE:
        if not os.path.exists(entry.path):
            continue
        size = _dir_size(entry.path)
        results.append({
            "path": entry.path,
            "category": entry.category,
            "description": entry.description,
            "size_bytes": size,
            "size_human": human_size(size),
            "cleanable": entry.cleanable,
        })
    results.sort(key=lambda x: x["size_bytes"], reverse=True)
    return results


# ============================================
# 2. Docker 运行状态分析
# ============================================

def analyze_docker() -> dict:
    """
    分析 Docker 当前状态：
    - 运行中/停止的容器
    - 所有镜像及其引用状态
    - 所有卷及其挂载状态
    - 网络列表
    """
    try:
        client = docker.from_env()
    except Exception:
        return {"error": "无法连接 Docker daemon"}

    containers = []
    used_image_ids = set()
    used_volumes = set()
    used_networks = set()

    # 容器
    for c in client.containers.list(all=True):
        mounts = []
        for m in c.attrs.get("Mounts", []):
            mounts.append({
                "source": m.get("Source", ""),
                "destination": m.get("Destination", ""),
                "type": m.get("Type", ""),
            })
            if m.get("Type") == "volume":
                used_volumes.add(m.get("Name"))
        for net_name in c.attrs.get("NetworkSettings", {}).get("Networks", {}):
            used_networks.add(net_name)

        containers.append({
            "name": c.name,
            "id": c.short_id,
            "status": c.status,
            "image": c.attrs.get("Config", {}).get("Image", ""),
            "size_rw": int(c.attrs.get("SizeRw", 0) or 0),
            "mounts": mounts,
        })
        used_image_ids.add(c.image.id)

    # 镜像
    images = []
    for img in client.images.list():
        images.append({
            "id": img.short_id,
            "tags": img.tags or ["<none>"],
            "size_bytes": int(img.attrs.get("Size", 0)),
            "in_use": img.id in used_image_ids,
            "dangling": not img.tags,
        })

    # 卷
    volumes = []
    for v in client.volumes.list():
        volumes.append({
            "name": v.name,
            "mountpoint": v.attrs.get("Mountpoint", ""),
            "in_use": v.name in used_volumes,
        })

    # 网络
    networks = []
    for n in client.networks.list():
        if n.name in ("bridge", "host", "none"):
            continue
        networks.append({
            "name": n.name,
            "in_use": n.name in used_networks,
        })

    return {
        "containers": containers,
        "images": images,
        "volumes": volumes,
        "networks": networks,
        "summary": {
            "running": sum(1 for c in containers if c["status"] == "running"),
            "stopped": sum(1 for c in containers if c["status"] != "running"),
            "unused_images": sum(1 for i in images if not i["in_use"]),
            "unused_volumes": sum(1 for v in volumes if not v["in_use"]),
        },
    }


# ============================================
# 3. 孤儿目录检测
# ============================================

def detect_orphan_dirs() -> list[dict]:
    """
    扫描用户自建 Docker 目录（如 /host/vol1/1000/docker/），
    对比实际存在的容器名，找出"目录存在但没有对应容器"的残留。
    """
    orphan_dirs = []
    docker_base = "/host/vol1/1000/docker"
    if not os.path.isdir(docker_base):
        return orphan_dirs

    # 获取所有实际容器名
    try:
        client = docker.from_env()
        existing_names = {c.name for c in client.containers.list(all=True)}
    except Exception:
        existing_names = set()

    # 遍历 docker_base 下的子目录
    for entry in os.listdir(docker_base):
        full = os.path.join(docker_base, entry)
        if not os.path.isdir(full):
            continue
        # 目录名可能和容器名一致，也可能是容器名的变体
        if entry not in existing_names:
            size = _dir_size(full)
            orphan_dirs.append({
                "path": full,
                "name": entry,
                "size_bytes": size,
                "size_human": human_size(size),
                "reason": "目录存在但无对应运行/已停止容器",
            })
    return orphan_dirs


# ============================================
# 4. 综合报告
# ============================================

def full_report() -> dict:
    """
    生成综合分析报告：
    - 磁盘占用概览
    - Docker 状态
    - 孤儿目录
    - 汇总可清理空间估算
    """
    disk = scan_disk_overview()
    docker_info = analyze_docker()
    orphans = detect_orphan_dirs()

    # 汇总可清理空间
    cleanable_disk = sum(d["size_bytes"] for d in disk if d["cleanable"])
    unused_images_size = sum(
        i["size_bytes"] for i in docker_info.get("images", []) if not i["in_use"]
    )
    orphan_size = sum(o["size_bytes"] for o in orphans)

    return {
        "disk_overview": disk,
        "docker": docker_info,
        "orphan_dirs": orphans,
        "estimate": {
            "cleanable_cache_bytes": cleanable_disk,
            "cleanable_cache_human": human_size(cleanable_disk),
            "unused_images_bytes": unused_images_size,
            "unused_images_human": human_size(unused_images_size),
            "orphan_dirs_bytes": orphan_size,
            "orphan_dirs_human": human_size(orphan_size),
            "total_estimate_bytes": cleanable_disk + unused_images_size + orphan_size,
            "total_estimate_human": human_size(cleanable_disk + unused_images_size + orphan_size),
        },
    }
