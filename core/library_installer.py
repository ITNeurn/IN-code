# -*- coding: utf-8 -*-
"""
库安装模块
==========
把第三方依赖安装进软件内置 venv（隔离环境），在后台线程执行。
界面通过"库安装模板页面"弹窗展示进度："正在安装所需库（库名）"。
"""
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

from .compiler import venv_pip


class LibraryInstallWorker(QThread):
    """后台安装单个 / 多个 Python 第三方库。

    信号：
      progress(str)          当前正在安装的库名（用于弹窗文字动态更新）
      log(str)               pip 输出日志
      one_done(str, bool)    单个库安装完成（库名, 是否成功）
      finished_all(bool)     全部完成（是否全部成功）
    """
    progress = pyqtSignal(str)
    log = pyqtSignal(str)
    one_done = pyqtSignal(str, bool)
    finished_all = pyqtSignal(bool)

    def __init__(self, packages: list[str], parent=None):
        super().__init__(parent)
        self.packages = packages

    def run(self):
        all_ok = True
        for pkg in self.packages:
            self.progress.emit(pkg)
            try:
                proc = subprocess.run(
                    venv_pip() + ["install", pkg],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=1800,
                )
                self.log.emit(proc.stdout + proc.stderr)
                ok = proc.returncode == 0
            except Exception as e:
                self.log.emit(f"安装 {pkg} 出错：{e}")
                ok = False
            all_ok = all_ok and ok
            self.one_done.emit(pkg, ok)
        self.finished_all.emit(all_ok)
