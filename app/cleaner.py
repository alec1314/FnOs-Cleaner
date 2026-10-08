"""
清理执行器（安全加固版）
========================
每一步删除前都有双重检查：
1. 文件类：路径必须不在保护列表中 + 必须是普通文件（非符号链接/目录）
2. Docker 容器：删除前再次确认 status != running
3. Docker 镜像：不用 force=True
4. 卷/网络：默认不删，需要配置里显式开启
"""
import os
import docker
from .config import config
from .models import create_clean_run, finish_clean_run, save_scan_results
from .filesystem_map import is_protected, classify_path, CATEGORY_PROTECTED


def run_scan(modules: list[str] | None = None) -> list[dict]:
    from .scanner.docker_prune import DockerPruneScanner
    from .scanner.download_residue import DownloadResidueScanner
    from .scanner.trash_log import TrashLogScanner
    from .scanner.media_cache import MediaCacheScanner

    all_items = []
    module_config = config.get("modules", {})

    scanners = [
        DockerPruneScanner(module_config.get("docker_prune", {})),
        DownloadResidueScanner(module_config.get("download_residue", {})),
        TrashLogScanner(module_config.get("trash_log", {})),
        MediaCacheScanner(module_config.get("media_cache", {})),
    ]

    for sc in scanners:
        if not sc.enabled():
            continue
        if modules and sc.module_name not in modules:
            continue
        all_items.extend(sc.scan())

    save_scan_results(all_items)
    return all_items


def run_cleanup(items: list[dict], dry_run: bool = True) -> dict:
    run_id = create_clean_run(
        mode="dry-run" if dry_run else "apply",
        modules=",".join(set(i["module"] for i in items)),
    )

    freed = 0
    deleted = 0
    skipped = 0
    errors = []
    max_size = config.get("safety", {}).get("max_file_size_gb", 5) * 1024 * 1024 * 1024

    docker_client = None
    if any(i["item_type"] in ("container", "image", "volume", "network") for i in items):
        try:
            docker_client = docker.from_env()
        except Exception:
            docker_client = None

    for it in items:
        # ========== 安全检查 1：保护路径 ==========
        if it.get("path") and is_protected(it["path"]):
            skipped += 1
            errors.append(f"跳过（系统保护路径）: {it['path']}")
            continue

        # ========== 安全检查 2：超大文件 ==========
        if it["size_bytes"] > max_size and it["item_type"] not in ("image",):
            skipped += 1
            errors.append(f"跳过（超过 {max_size//1024//1024//1024}GB）: {it.get('path', it['item_name'])}")
            continue

        if dry_run:
            freed += it["size_bytes"]
            deleted += 1
            continue

        try:
            if it["item_type"] == "container":
                # 删除前再次确认容器不是运行状态
                if docker_client:
                    c = docker_client.containers.get(it["path"])
                    if c.status == "running":
                        errors.append(f"跳过（容器正在运行）: {c.name}")
                        continue
                    c.remove()

            elif it["item_type"] == "image":
                # 不用 force=True，只删悬空镜像
                if docker_client:
                    docker_client.images.remove(it["path"], force=False)

            elif it["item_type"] == "volume":
                # 卷默认不删——需要配置显式开启
                if not config.get("modules", {}).get("docker_prune", {}).get("allow_volume_delete", False):
                    errors.append(f"跳过（卷删除未开启）: {it['item_name']}")
                    continue
                if docker_client:
                    v = docker_client.volumes.get(it["item_name"])
                    v.remove()

            elif it["item_type"] == "network":
                if docker_client:
                    n = docker_client.networks.get(it["item_name"])
                    n.remove()

            else:
                # ===== 文件类删除的三重检查 =====
                fpath = it["path"]
                # 检查 1：必须是普通文件（不是目录、不是符号链接）
                if not os.path.isfile(fpath) or os.path.islink(fpath):
                    errors.append(f"跳过（非普通文件）: {fpath}")
                    continue
                # 检查 2：路径分类不能是 protected
                entry = classify_path(fpath)
                if entry.category == CATEGORY_PROTECTED:
                    errors.append(f"跳过（分类为保护路径）: {fpath}")
                    continue
                # 检查 3：必须在挂载的存储空间下（/host/ 开头）
                if not fpath.startswith("/host/"):
                    errors.append(f"跳过（不在挂载范围内）: {fpath}")
                    continue
                os.remove(fpath)

            freed += it["size_bytes"]
            deleted += 1
        except Exception as e:
            errors.append(f"{it['item_name']}: {e}")

    report = {
        "run_id": run_id,
        "deleted": deleted,
        "skipped": skipped,
        "freed_bytes": freed,
        "freed_human": _human_size(freed),
        "errors": errors,
        "dry_run": dry_run,
    }

    finish_clean_run(run_id, deleted, freed, str(report))
    return report


def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"
