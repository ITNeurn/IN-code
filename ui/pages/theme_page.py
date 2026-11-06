# -*- coding: utf-8 -*-
"""设置 - 主题设置页
==================
参考华为 HarmonyOS 设置页：大标题 + 说明文字 + 圆角卡片，卡片内左侧为
功能名称与描述、右侧为胶囊开关。
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame)

from ..widgets.toggle_switch import ToggleSwitch


class ThemePage(QWidget):
    """主题设置：目前提供"沉浸光感"开关。"""

    def __init__(self, settings, on_change=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._on_change = on_change

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 16, 28, 16)
        lay.setSpacing(4)

        title = QLabel("主题")
        title.setProperty("h1", True)
        lay.addWidget(title)
        sub = QLabel("个性化你的编程空间")
        sub.setProperty("hint", True)
        lay.addWidget(sub)
        lay.addSpacing(16)

        # ---------------- 沉浸光感卡片
        card = QFrame()
        card.setProperty("hcard", True)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(14)

        icon = QLabel("✦")
        icon.setProperty("hicon", True)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(38, 38)
        cl.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        txt = QVBoxLayout()
        txt.setSpacing(5)
        name = QLabel("沉浸光感")
        name.setProperty("h2", True)
        desc = QLabel("开启后，窗口四周会浮现随呼吸缓缓流动的青绿极光，"
                      "让界面更有空间层次与沉浸感。")
        desc.setProperty("hint", True)
        desc.setWordWrap(True)
        txt.addWidget(name)
        txt.addWidget(desc)
        cl.addLayout(txt, 1)

        self.switch = ToggleSwitch(bool(settings.get("immersive_glow", False)))
        self.switch.toggled.connect(self._toggle)
        cl.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(card)
        lay.addStretch(1)

    def _toggle(self, on: bool):
        self.settings.set("immersive_glow", on)
        if self._on_change:
            self._on_change(on)
