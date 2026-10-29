# -*- coding: utf-8 -*-
"""
全局配置管理
============
使用 JSON 文件持久化用户配置，存储于用户目录下的 .incode 文件夹，
避免污染系统环境，也不需要管理员权限。
"""
import json
import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------- 全局路径
APP_ROOT = Path(__file__).resolve().parent.parent          # 软件根目录
ASSETS_DIR = APP_ROOT / "assets"                            # 内置资源（视频等）
APP_DATA_DIR = Path.home() / ".incode"                      # 用户数据目录

# 兼容旧版本：若存在旧 .creativecoder 数据目录且新目录不存在，则整体迁移
_LEGACY_DATA_DIR = Path.home() / ".creativecoder"
if _LEGACY_DATA_DIR.exists() and not APP_DATA_DIR.exists():
    try:
        shutil.move(str(_LEGACY_DATA_DIR), str(APP_DATA_DIR))
    except OSError:
        pass

RUNTIME_DIR = APP_DATA_DIR / "runtime"                      # 隔离运行环境目录
VENV_DIR = RUNTIME_DIR / "venv"                             # 内置 Python 虚拟环境
CONFIG_FILE = APP_DATA_DIR / "config.json"                  # 配置文件

# 软件版本
APP_VERSION = "2.0.3"
APP_NAME = "IN-code"

# 默认配置
DEFAULT_CONFIG = {
    # API 接口管理
    "api_key": "",                                  # DeepSeek API 密钥
    "api_base": "https://api.deepseek.com",         # OpenAI 兼容接口地址
    "cloud_model": "deepseek-chat",                 # 云端模型名
    # 模型模式：cloud = 云端 DeepSeek API；local = 本地模型（内嵌引擎/Ollama）
    "model_mode": "cloud",
    # 本地后端：embedded = 软件内嵌 llama-server + 内置GGUF；ollama = 本机 Ollama
    "local_backend": "embedded",
    # 本地模型管理
    "local_model": "deepseek-r1:7b",                # 当前选中本地模型
    "ollama_host": "http://localhost:11434",        # Ollama 服务地址
    # 默认存储位置（本地 AI 模型存储磁盘路径，默认 C 盘用户目录）
    "model_storage": str(Path.home() / ".incode" / "models"),
    # 超能模式
    "super_mode": False,                            # 是否已激活
    "super_lib_dir": "",                            # 超能模式库安装目录
    "super_moe": False,                             # 是否安装 MoE 模型
    # 编程语言
    "language": "python",                           # python / c / cpp
    # Github 跳转地址
    "github_url": "https://github.com",
}


class Settings:
    """简单的 JSON 配置读写封装（单例风格使用）。"""

    def __init__(self):
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        self._data = dict(DEFAULT_CONFIG)
        self.load()

    # ------------------------------------------------------------ 持久化
    def load(self):
        """从磁盘加载配置，失败时使用默认配置。"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
        except (json.JSONDecodeError, OSError):
            # 配置文件损坏时回退到默认值，保证软件可启动
            pass

    def save(self):
        """把当前配置写回磁盘。"""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------ 访问
    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self.set(key, value)
