# -*- coding: utf-8 -*-
"""设置 - 默认存储位置页：选择本地 AI 模型存储磁盘路径，默认 C 盘，可自定义。"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QFileDialog)


class StoragePage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        lay.addWidget(QLabel("本地 AI 模型存储位置"))
        row = QHBoxLayout()
        row.addWidget(QLabel("💾 ："))
        self.edit = QLineEdit(settings.get("model_storage"))
        btn = QPushButton("浏览…")
        btn.clicked.connect(self._browse)
        row.addWidget(self.edit, 1)
        row.addWidget(btn)
        lay.addLayout(row)

        btn_save = QPushButton("保存")
        btn_save.setProperty("primary", True)
        btn_save.clicked.connect(self._save)
        lay.addWidget(btn_save)
        lay.addStretch(1)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择存储位置", self.edit.text())
        if d:
            self.edit.setText(d)

    def _save(self):
        self.settings.set("model_storage", self.edit.text().strip())
