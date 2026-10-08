"""APScheduler 定时任务"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .config import config
from .cleaner import run_scan, run_cleanup

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def scheduled_cleanup():
    """定时任务：扫描后自动执行清理（dry-run 模式，结果只写报告）"""
    logger.info("定时清理任务触发")
    items = run_scan()
    result = run_cleanup(items, dry_run=config.get("safety", {}).get("dry_run_default", True))
    logger.info("定时清理完成: 删除 %d 项, 释放 %s", result["deleted"], result["freed_human"])


def init_scheduler():
    sched_cfg = config.get("schedule", {})
    if not sched_cfg.get("enabled"):
        return
    cron_expr = sched_cfg.get("cron", "0 3 * * 0")
    parts = cron_expr.split()
    if len(parts) == 5:
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2],
            month=parts[3], day_of_week=parts[4],
        )
        scheduler.add_job(scheduled_cleanup, trigger, id="scheduled_cleanup")
    scheduler.start()
    logger.info("定时任务已启动: %s", cron_expr)
