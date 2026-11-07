# -*- coding: utf-8 -*-
"""设置 - 主题设置页
==================
参考华为 HarmonyOS 沉浸光感设计规范：
  光不是盖在界面上的滤镜，而是界面"之下"的空间光；面板变成半透明介质，
  环境光从背后透出并沿边缘流转。官方提供弱档 / 均衡档 / 强档三档强度。

页面结构：大标题 + 说明文字 + 圆角卡片（左侧名称与描述、右侧胶囊开关），
强度选择为三段式分段控件。
"""
import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame)

from ..widgets.toggle_switch import ToggleSwitch
from ..widgets.light_stage import LightStage, LEVELS as LIGHT_LEVELS
from ..widgets.segmented_control import SegmentedControl

LEVELS = [("weak", "弱档"), ("balanced", "均衡档"), ("strong", "强档")]
LEVEL_HINTS = {
    "weak": "收敛光彩，保持高对比度，核心信息始终清晰锐利。",
    "balanced": "通透与对比的平衡，环境光沿边缘柔和流转，勾勒层次。",
    "strong": "强化光影折射层次，叠加粒子流转与空间光效，氛围浓郁深邃。",
}


class ThemePage(QWidget):
    """主题设置：沉浸光感开关 + 三档强度。"""

    def __init__(self, settings, on_change=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._on_change = on_change

        # 本页自绘光场背景，方便在设置弹窗内直接预览光感效果
        self.setObjectName("themeRoot")
        self._glow = bool(settings.get("immersive_glow", False))
        self._level = settings.get("immersive_glow_level", "balanced")
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        if self._glow:
            self._timer.start()

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

        # ---------------- 沉浸光感
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
        desc = QLabel("界面元素不再是实色填充，而是如薄雾般通透的介质："
                      "环境光从底层透出，沿面板边缘柔和流转。")
        desc.setProperty("hint", True)
        desc.setWordWrap(True)
        txt.addWidget(name)
        txt.addWidget(desc)
        cl.addLayout(txt, 1)

        self.switch = ToggleSwitch(bool(settings.get("immersive_glow", False)))
        self.switch.toggled.connect(self._toggle)
        cl.addWidget(self.switch, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(card)
        lay.addSpacing(12)

        # ---------------- 光感强度
        self.level_card = QFrame()
        self.level_card.setProperty("hcard", True)
        ll = QVBoxLayout(self.level_card)
        ll.setContentsMargins(20, 18, 20, 18)
        ll.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(14)
        licon = QLabel("☼")
        licon.setProperty("hicon", True)
        licon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        licon.setFixedSize(38, 38)
        head.addWidget(licon, 0, Qt.AlignmentFlag.AlignTop)

        htxt = QVBoxLayout()
        htxt.setSpacing(5)
        lname = QLabel("光感强度")
        lname.setProperty("h2", True)
        self.level_hint = QLabel(LEVEL_HINTS["balanced"])
        self.level_hint.setProperty("hint", True)
        self.level_hint.setWordWrap(True)
        htxt.addWidget(lname)
        htxt.addWidget(self.level_hint)
        head.addLayout(htxt, 1)
        ll.addLayout(head)

        bar = SegmentedControl(LEVELS)
        bar.set_selected_key(settings.get("immersive_glow_level", "balanced"))
        bar.set_on_change(self._set_level)
        ll.addWidget(bar)
        self._seg = bar

        lay.addWidget(self.level_card)
        lay.addStretch(1)

        self._sync_enabled()

    # ------------------------------------------------------------ 交互
    def _toggle(self, on: bool):
        self.settings.set("immersive_glow", on)
        self._glow = on
        if on:
            self._timer.start()
        else:
            self._timer.stop()
        self.update()
        self._sync_enabled()
        if self._on_change:
            self._on_change(on, self._current_level())

    def _set_level(self, level: str):
        self.settings.set("immersive_glow_level", level)
        self._level = level
        self.update()
        self.level_hint.setText(LEVEL_HINTS.get(level, ""))
        if self._on_change:
            self._on_change(self.switch.isChecked(), level)

    def _current_level(self) -> str:
        return self._seg.current_key()

    def _sync_enabled(self):
        on = self.switch.isChecked()
        self.level_card.setEnabled(on)
        self.level_hint.setText(
            LEVEL_HINTS[self._current_level()] if on
            else "开启沉浸光感后可调节光感强度。")

    # ------------------------------------------------------------ 光场预览
    def _tick(self):
        self._t += 0.045
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000"))
        if not self._glow:
            p.end()
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            p.end()
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = LIGHT_LEVELS.get(self._level, LIGHT_LEVELS["balanced"])["aurora"]
        t = self._t
        LightStage._aura(p, w * 0.55, -h * 0.18, max(w, h) * 0.85,
                         "#1abc9c", int(150 * k))
        LightStage._aura(p, -w * 0.10, h * 0.05, w * 0.62,
                         "#3d6bff", int(130 * k))
        LightStage._aura(p, w * 0.95, h * 0.95, w * 0.60,
                         "#7ee787", int(105 * k))
        LightStage._aura(p, w * (0.45 + 0.04 * math.sin(t * 0.4)),
                         h * 0.55, max(w, h) * 0.55, "#14b8a6", int(70 * k))
        p.end()
