# -*- coding: utf-8 -*-
"""
超能模式模块
============
超能模式 = 本地离线能力包：后台下载上百个 Python 第三方库 + 可选 MoE 模型。
设计原则：
  1. 所有大体积下载都必须经过用户多重确认（弹窗流程见 ui/dialogs/super_mode_wizard.py）。
  2. 下载任务全部后台执行，不阻塞界面。
  3. 下载前检查磁盘剩余空间，不足时明确提示。
"""
import shutil
import subprocess
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from config.settings import Settings, APP_DATA_DIR
from .compiler import venv_pip

# 超能模式预装的第三方库清单（可按需扩展）
SUPER_PACKAGES = [
    "numpy", "pandas", "matplotlib", "scipy", "scikit-learn",
    "requests", "httpx", "beautifulsoup4", "lxml", "openpyxl",
    "pillow", "opencv-python-headless", "pygame", "pyqt6",
    "flask", "fastapi", "uvicorn", "sqlalchemy", "pymysql",
    "tqdm", "rich", "loguru", "pydantic", "click",
    "pytest", "black", "pyinstaller", "wheel", "setuptools",
]

# MoE 模型（Ollama 模型名，体积很大，用户可选择不装）
MOE_MODEL = "deepseek-r1:14b"

# 预估磁盘占用（字节），用于空间检查
SUPER_LIB_ESTIMATE = 6 * 1024 ** 3     # 第三方库约 6GB
MOE_ESTIMATE = 10 * 1024 ** 3          # MoE 模型约 10GB


class SuperModeManager:
    """超能模式状态管理：激活标记、磁盘空间检查、关闭。"""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def active(self) -> bool:
        return bool(self.settings.get("super_mode", False))

    def activate(self, lib_dir: str, install_moe: bool):
        self.settings.set("super_mode", True)
        self.settings.set("super_lib_dir", lib_dir)
        self.settings.set("super_moe", install_moe)

    def deactivate(self):
        """关闭超能模式（不删除已下载文件，只关闭状态）。"""
        self.settings.set("super_mode", False)

    # ------------------------------------------------------------ 磁盘检查
    @staticmethod
    def check_disk_space(path: str, need_moe: bool) -> tuple[bool, str]:
        """检查目标磁盘剩余空间是否足够。返回 (是否足够, 提示文字)。"""
        need = SUPER_LIB_ESTIMATE + (MOE_ESTIMATE if need_moe else 0)
        try:
            usage = shutil.disk_usage(Path(path).anchor or path)
        except OSError:
            return False, "无法读取目标磁盘信息"
        if usage.free < need:
            return False, (f"磁盘剩余空间不足：需要约 {need // 1024 ** 3}GB，"
                           f"当前剩余 {usage.free // 1024 ** 3}GB")
        return True, f"空间充足（剩余 {usage.free // 1024 ** 3}GB）"


class SuperDownloadWorker(QThread):
    """超能模式后台下载线程：批量 pip 安装 + 可选 ollama pull MoE 模型。

    信号：
      progress(str)          当前下载项描述（用于"库安装模板页面"动态文字）
      finished_all(bool)     全部结束
    """
    progress = pyqtSignal(str)
    finished_all = pyqtSignal(bool)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings

    def run(self):
        ok_all = True
        # 1) 批量安装第三方库
        for pkg in SUPER_PACKAGES:
            self.progress.emit(pkg)
            try:
                proc = subprocess.run(venv_pip() + ["install", pkg],
                                      capture_output=True, timeout=3600)
                ok_all = ok_all and (proc.returncode == 0)
            except Exception:
                ok_all = False
        # 2) 可选：下载 MoE 模型
        if self.settings.get("super_moe"):
            self.progress.emit(MOE_MODEL)
            ollama = shutil.which("ollama")
            if ollama:
                try:
                    proc = subprocess.run([ollama, "pull", MOE_MODEL],
                                          capture_output=True, timeout=86400)
                    ok_all = ok_all and (proc.returncode == 0)
                except Exception:
                    ok_all = False
            else:
                ok_all = False
        self.finished_all.emit(ok_all)
