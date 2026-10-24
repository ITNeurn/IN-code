# -*- coding: utf-8 -*-
"""设置 - API接口管理页：填写云端 AI 模型 API 密钥 + 显示 API 余额。"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton)
from PyQt6.QtCore import QThread, pyqtSignal

from core.ai_client import fetch_balance


class _BalanceWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def run(self):
        self.done.emit(fetch_balance(self.settings))


class ApiPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # 云端 AI 模型 API 密钥
        lay.addWidget(QLabel("云端 AI 模型 API 密钥："))
        row = QHBoxLayout()
        self.key_edit = QLineEdit(settings.get("api_key"))
        self.key_edit.setPlaceholderText("请输入 DeepSeek API 密钥（sk-…）")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        btn_save = QPushButton("保存")
        btn_save.setProperty("primary", True)
        btn_save.clicked.connect(self._save)
        row.addWidget(self.key_edit, 1)
        row.addWidget(btn_save)
        lay.addLayout(row)

        # 云端 AI 模型 API 余额
        row2 = QHBoxLayout()
        self.balance_label = QLabel("云端 AI 模型 API 余额：未查询")
        btn_refresh = QPushButton("查询余额")
        btn_refresh.clicked.connect(self._refresh)
        row2.addWidget(self.balance_label, 1)
        row2.addWidget(btn_refresh)
        lay.addLayout(row2)

        lay.addStretch(1)
        self._worker = None

    def _save(self):
        self.settings.set("api_key", self.key_edit.text().strip())

    def _refresh(self):
        self._save()
        self.balance_label.setText("云端 AI 模型 API 余额：查询中…")
        self._worker = _BalanceWorker(self.settings)
        self._worker.done.connect(
            lambda s: self.balance_label.setText(f"云端 AI 模型 API 余额：{s}"))
        self._worker.start()
