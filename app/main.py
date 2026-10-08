"""Flask 入口"""
import os
from flask import Flask, render_template, request, jsonify
from .models import init_db, get_recent_runs
from .cleaner import run_scan, run_cleanup
from .scheduler import init_scheduler
from .config import config
from .analyzer import full_report

# 指定模板和静态文件路径（相对于 app/ 目录）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_BASE_DIR, "web", "templates"),
    static_folder=os.path.join(_BASE_DIR, "web", "static"),
)

# 启动时初始化（替代废弃的 before_first_request）
_init_done = False


def _ensure_init():
    global _init_done
    if not _init_done:
        init_db()
        init_scheduler()
        _init_done = True


@app.route("/")
def dashboard():
    _ensure_init()
    return render_template("dashboard.html")


@app.route("/api/scan", methods=["POST"])
def api_scan():
    _ensure_init()
    data = request.get_json(silent=True) or {}
    modules = data.get("modules")
    items = run_scan(modules)
    total_size = sum(i["size_bytes"] for i in items)
    return jsonify({
        "items": items,
        "count": len(items),
        "total_size_bytes": total_size,
        "total_size_human": _human_size(total_size),
    })


@app.route("/api/cleanup", methods=["POST"])
def api_cleanup():
    _ensure_init()
    data = request.get_json(silent=True) or {}
    items = data.get("items", [])
    dry_run = data.get("dry_run", True)
    result = run_cleanup(items, dry_run=dry_run)
    return jsonify(result)


@app.route("/api/runs")
def api_runs():
    _ensure_init()
    return jsonify(get_recent_runs())


@app.route("/api/analyze")
def api_analyze():
    _ensure_init()
    return jsonify(full_report())


def _human_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


if __name__ == "__main__":
    _ensure_init()
    port = config.get("web", {}).get("port", 7878)
    app.run(host="0.0.0.0", port=port, debug=True)
