# -*- coding: utf-8 -*-
"""设置 - 云端大模型API获取页：展示 DeepSeek 平台网址。"""
import webbrowser

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton


class CloudApiPage(QWidget):
    URL = "https://platform.deepseek.com/"

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lab = QLabel(f"Deepseek网址：{self.URL}")
        lab.setTextInteractionFlags(lab.textInteractionFlags())
        from PyQt6.QtCore import Qt
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setStyleSheet("font-size:14px;")
        lay.addWidget(lab)
        btn = QPushButton("在浏览器中打开")
        btn.setProperty("primary", True)
        btn.clicked.connect(lambda: webbrowser.open(self.URL))
        lay.addWidget(btn)
        lay.addStretch(1)
