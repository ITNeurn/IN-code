# -*- coding: utf-8 -*-
"""设置 - 版本信息页：显示软件版本。"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from config.settings import APP_VERSION, APP_NAME


class VersionPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lab = QLabel(f"软件版本：{APP_VERSION}")
        lab.setStyleSheet("font-size:15px;")
        lay.addWidget(lab)
        lay.addWidget(QLabel(f"{APP_NAME} —— 用自然语言逻辑学编程"))
        lay.addStretch(1)
