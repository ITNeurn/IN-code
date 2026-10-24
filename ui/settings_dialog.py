# -*- coding: utf-8 -*-
"""
设置主页面
==========
对照《设置主页面.pptx》：左侧大标题"设置" + 侧边菜单列表，右侧内容区。
菜单项（自上而下）：
  默认存储位置 / API接口管理 / 本地模型管理 / 云端大模型API获取 / 版本信息 / 超能模式
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QListWidget,
                             QStackedWidget, QLabel, QWidget)

from .pages import (StoragePage, ApiPage, LocalModelPage,
                    CloudApiPage, VersionPage, SuperModePage)

MENU = ["默认存储位置", "API接口管理", "本地模型管理",
        "云端大模型API获取", "版本信息", "超能模式"]


class SettingsDialog(QDialog):
    """设置主对话框：侧边菜单 + 页面堆栈。"""

    def __init__(self, settings, parent=None, initial: str = None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("设置")
        self.resize(860, 560)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------------- 左侧：标题 + 侧边菜单
        side = QWidget()
        side.setFixedWidth(190)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 8, 0, 8)
        title = QLabel("设置")
        title.setStyleSheet("font-size:22px;font-weight:bold;padding:4px 16px;")
        sl.addWidget(title)
        self.menu = QListWidget()
        self.menu.setProperty("sidebar", True)
        self.menu.addItems(MENU)
        sl.addWidget(self.menu, 1)
        root.addWidget(side)

        # ---------------- 右侧：页面堆栈
        self.stack = QStackedWidget()
        self.pages = [
            StoragePage(settings),
            ApiPage(settings),
            LocalModelPage(settings),
            CloudApiPage(settings),
            VersionPage(settings),
            SuperModePage(settings),
        ]
        for p in self.pages:
            self.stack.addWidget(p)
        root.addWidget(self.stack, 1)

        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)
        # 支持外部指定初始页（如"AI设置"导航按钮直达 API 接口管理）
        idx = MENU.index(initial) if initial in MENU else 0
        self.menu.setCurrentRow(idx)
