"""配置加载模块"""
import os
import yaml

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/app/config.yaml")


def load_config():
    """读取 YAML 配置文件，返回 dict"""
    if not os.path.exists(CONFIG_PATH):
        # 没有配置文件时用默认值
        return _default_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or _default_config()


def _default_config():
    return {
        "web": {"port": 7878, "password": ""},
        "schedule": {"enabled": False, "cron": "0 3 * * 0"},
        "safety": {"max_file_size_gb": 5, "dry_run_default": True},
        "modules": {},
    }


config = load_config()
