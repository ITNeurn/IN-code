# -*- coding: utf-8 -*-
"""设置 - 版本信息页：显示版本 + 在线检查更新（多线程分块下载、断点续传、sha256 校验）。"""
import sys

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QProgressBar, QMessageBox)

from config.settings import APP_VERSION, APP_NAME
from core.updater import UpdateWorker, apply_and_restart


class VersionPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._worker: UpdateWorker | None = None

        lay = QVBoxLayout(self)
        lab = QLabel(f"软件版本：{APP_VERSION}")
        lab.setStyleSheet("font-size:15px;")
        lay.addWidget(lab)
        lay.addWidget(QLabel(f"{APP_NAME} —— 用自然语言逻辑学编程"))

        self.check_btn = QPushButton("检查更新")
        self.check_btn.clicked.connect(self._check)
        lay.addWidget(self.check_btn)

        self.stage_label = QLabel("")
        lay.addWidget(self.stage_label)

        self.bar = QProgressBar()
        self.bar.hide()
        lay.addWidget(self.bar)
        lay.addStretch(1)

    def _check(self):
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self, "在线更新", "源码运行不支持在线更新，请使用 git pull 获取最新代码。")
            return
        if self._worker and self._worker.isRunning():
            return
        self.check_btn.setEnabled(False)
        self.bar.hide()
        self._worker = UpdateWorker(self)
        self._worker.stage.connect(self.stage_label.setText)
        self._worker.progress.connect(self._on_progress)
        self._worker.no_update.connect(self._on_no_update)
        self._worker.need_update.connect(self._on_need_update)
        self._worker.failed.connect(self._on_failed)
        self._worker.ready.connect(self._on_ready)
        self._worker.start()

    def _on_progress(self, done: int, total: int):
        if not self.bar.isVisible():
            self.bar.show()
        self.bar.setMaximum(max(total, 1))
        self.bar.setValue(done)
        self.stage_label.setText(
            f"正在下载更新包… {done / 1048576:.1f} / {total / 1048576:.1f} MB")

    def _on_no_update(self):
        self.check_btn.setEnabled(True)
        self.stage_label.setText(f"当前已是最新版本（v{APP_VERSION}）")

    def _on_need_update(self, info: dict):
        asset = info["asset"]
        ret = QMessageBox.question(
            self, "发现新版本",
            f"发现新版本 v{info['latest']}（当前 v{APP_VERSION}）\n\n"
            f"更新包大小：{asset['size'] / 1048576:.1f} MB（增量包，无需重下完整安装包）\n"
            f"将使用多线程下载并校验完整性。\n\n是否立即下载并更新？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            self._worker.download(asset)
        else:
            self.check_btn.setEnabled(True)
            self.stage_label.setText("已取消更新")

    def _on_failed(self, msg: str):
        self.check_btn.setEnabled(True)
        self.bar.hide()
        self.stage_label.setText(f"更新失败：{msg}")

    def _on_ready(self, staging):
        ret = QMessageBox.question(
            self, "更新就绪",
            "更新包已下载并通过完整性校验。\n\n现在重启软件完成更新吗？\n"
            "（旧版本会自动备份为 .bak，更新失败可手动回滚）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            apply_and_restart(staging)
        else:
            self.check_btn.setEnabled(True)
            self.stage_label.setText("更新已就绪，将在下次手动确认后应用")
