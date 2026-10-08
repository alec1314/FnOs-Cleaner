"""
fnOS 固定目录基线地图（安全版）
================================
安全原则：宁可少删，不可删错。

- protected 路径：绝对不碰，即使配置里勾了也跳过
- report_only 路径：只在报告里显示占用大小，不自动删除
- cleanable 路径：经过验证安全、删除后系统会自动重建的缓存类

路径准确性说明：
- ✅ 已从飞牛官方文档/社区帖子确认的路径
- ⚠️ 基于 Debian 通用布局推测，需在实际 NAS 上验证
"""

# 路径分类
CATEGORY_PROTECTED = "protected"       # 系统关键路径，绝不碰
CATEGORY_SYSTEM_APP = "system_app"     # 飞牛官方应用数据
CATEGORY_APP_RUNTIME = "app_runtime"   # FPK 应用运行时数据
CATEGORY_USER_DATA = "user_data"      # 用户文件（不自动清理）
CATEGORY_DOCKER_ROOT = "docker_root"  # Docker 数据根
CATEGORY_REPORT_ONLY = "report_only"   # 只报告占用，不自动删
CATEGORY_CLEANABLE = "cleanable"      # 经验证可安全删除（删了会自动重建）
CATEGORY_UNKNOWN = "unknown"           # 未识别路径——默认不删


class FnosPath:
    def __init__(self, path, category, description, cleanable=False, verified=True):
        self.path = path
        self.category = category
        self.description = description
        self.cleanable = cleanable
        self.verified = verified  # 路径是否已从官方渠道确认

    def to_dict(self):
        return {
            "path": self.path,
            "category": self.category,
            "description": self.description,
            "cleanable": self.cleanable,
            "verified": self.verified,
        }


# ============================================
# fnOS 标准目录基线（容器内挂载路径前缀为 /host）
# ============================================

BASELINE = [
    # ===== 🔒 系统保护路径（绝对不碰）=====
    FnosPath("/host/usr/local/apps", CATEGORY_PROTECTED,
             "飞牛系统应用根目录（trim.media/trim.photos/trim.vm）", verified=True),
    FnosPath("/host/etc/docker", CATEGORY_PROTECTED,
             "Docker daemon 配置目录", verified=True),
    FnosPath("/host/var/apps", CATEGORY_PROTECTED,
             "FPK 应用安装目录（生命周期脚本）", verified=True),
    FnosPath("/host/boot", CATEGORY_PROTECTED,
             "系统引导分区", verified=True),
    FnosPath("/host/etc", CATEGORY_PROTECTED,
             "系统配置目录", verified=True),

    # ===== ⚙️ FPK 应用运行时（只报告，不自动删）=====
    FnosPath("/host/vol1/@appdata", CATEGORY_APP_RUNTIME,
             "FPK 应用运行时数据（各应用配置/数据库）", verified=True),
    FnosPath("/host/vol1/@appmeta", CATEGORY_APP_RUNTIME,
             "FPK 应用元数据", verified=True),
    # @apptemp：应用运行中临时文件，删了可能导致应用异常，改为只报告
    FnosPath("/host/vol1/@apptemp", CATEGORY_REPORT_ONLY,
             "FPK 应用临时文件（只报告，需确认应用已停止后再手动清理）", verified=True),

    # ===== 🐳 Docker 数据根 =====
    FnosPath("/host/vol1/docker", CATEGORY_DOCKER_ROOT,
             "Docker data-root（镜像/容器/卷/构建缓存）——通过 Docker API 操作，不直接删文件",
             verified=True),

    # ===== 📁 用户主目录（不自动碰）=====
    FnosPath("/host/vol1/1000", CATEGORY_USER_DATA,
             "默认管理员用户主目录", verified=True),
    FnosPath("/host/vol1/1000/appshare", CATEGORY_USER_DATA,
             "应用共享文件夹", verified=True),
    FnosPath("/host/vol1/1000/docker", CATEGORY_USER_DATA,
             "用户自建 Docker 容器目录（按应用分子目录）", verified=True),

    # ===== 🧹 经验证可安全清理的缓存（删了系统会自动重建）=====
    # 缩略图缓存：删了之后文件管理器会重新生成，不影响原文件
    FnosPath("/host/vol1/1000/.thumbnail", CATEGORY_CLEANABLE,
             "文件管理器缩略图缓存（删除后自动重建，不影响原文件）",
             cleanable=True, verified=False),  # ⚠️ 路径需在实际 NAS 确认

    # ===== 🚫 只报告、不自动删的"看起来像垃圾但实际不能删"的 =====
    # 回收站：用户可能还想恢复，绝不自动清空
    FnosPath("/host/vol1/1000/@recycle", CATEGORY_REPORT_ONLY,
             "共享文件夹回收站（只报告大小，需用户手动确认清空）", verified=False),

    # 用户缓存目录：里面可能有正在使用的缓存，不自动删
    FnosPath("/host/vol1/1000/.cache", CATEGORY_REPORT_ONLY,
             "用户级缓存目录（只报告，不自动删）", verified=False),
]


# 绝对禁止删除的路径前缀（即使配置里勾了也跳过）
PROTECTED_PREFIXES = [e.path for e in BASELINE if e.category == CATEGORY_PROTECTED]


def classify_path(path: str) -> FnosPath:
    """最长前缀匹配分类"""
    best = None
    best_len = 0
    for entry in BASELINE:
        if path.startswith(entry.path) and len(entry.path) > best_len:
            best = entry
            best_len = len(entry.path)
    if best is None:
        return FnosPath(path, CATEGORY_UNKNOWN, "未识别路径——默认不删除")
    return best


def is_protected(path: str) -> bool:
    """检查路径是否在保护列表中"""
    for p in PROTECTED_PREFIXES:
        if path.startswith(p):
            return True
    return False


def get_cleanable_paths() -> list[FnosPath]:
    return [e for e in BASELINE if e.cleanable]


def get_protected_paths() -> list[FnosPath]:
    return [e for e in BASELINE if e.category == CATEGORY_PROTECTED]
