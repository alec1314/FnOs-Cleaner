"""SQLite 数据模型：扫描记录、清理报告"""
import os
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("DATA_DIR", "/data") + "/fnos_cleaner.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            module TEXT NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            size_bytes INTEGER DEFAULT 0,
            path TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS clean_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            mode TEXT NOT NULL,
            modules TEXT,
            total_items INTEGER DEFAULT 0,
            freed_bytes INTEGER DEFAULT 0,
            report TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_scan_results(items: list[dict]):
    """批量保存扫描结果"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    for it in items:
        c.execute("""
            INSERT INTO scans (created_at, module, item_type, item_name, size_bytes, path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (now, it["module"], it["item_type"], it["item_name"],
              it["size_bytes"], it.get("path", "")))
    conn.commit()
    conn.close()


def create_clean_run(mode: str, modules: str) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO clean_runs (started_at, mode, modules) VALUES (?, ?, ?)
    """, (datetime.now().isoformat(), mode, modules))
    run_id = c.lastrowid
    conn.commit()
    conn.close()
    return run_id


def finish_clean_run(run_id: int, total_items: int, freed_bytes: int, report: str):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        UPDATE clean_runs SET finished_at=?, total_items=?, freed_bytes=?, report=?
        WHERE id=?
    """, (datetime.now().isoformat(), total_items, freed_bytes, report, run_id))
    conn.commit()
    conn.close()


def get_recent_runs(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM clean_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
