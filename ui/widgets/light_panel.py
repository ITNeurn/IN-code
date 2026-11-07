# -*- coding: utf-8 -*-
"""沉浸光感 - 毛玻璃面板
=========================
华为沉浸光感的核心：面板不是半透明色板，而是"毛玻璃介质"——
背后的光场被真实模糊后透出，再叠加深色蒙版。

绘制流程（开启光感时）：
  1. 从 LightStage 取已模糊的背景 _bg_pixmap
  2. 截取面板背后的那一块模糊光场
  3. 按圆角裁剪切到面板上（= 模糊的彩色光透出）
  4. 叠加深色半透明蒙版（控制通透度）
  5. 顶部漫反射高光 + 沿轮廓流转的锥形描边

关闭光感时与原 QSS 面板一致（实色 #1e1f24）。
"""
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QConicalGradient,
                         QLinearGradient, QPainterPath, QPixmap)
from PyQt6.QtWidgets import QFrame

RADIUS = 12

# 档位 -> (深色蒙版不透明度, 描边亮度, 轮廓光速度)
_LEVELS = {
    "weak":    (150, 0.7, 0.5),
    "balanced": (100, 1.1, 0.8),
    "strong":   (60, 1.4, 1.2),
}


class LightPanel(QFrame):
    """支持沉浸光感的毛玻璃卡片容器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glassPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._on = False
        self._tint = 100       # 深色蒙版不透明度
        self._border = 1.1
        self._speed = 0.8
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ 开关
    def set_glow(self, enabled: bool, level: str = "balanced"):
        tint, border, speed = _LEVELS.get(level, _LEVELS["balanced"])
        self._on = bool(enabled)
        self._tint = tint
        self._border = border
        self._speed = speed
        if self._on:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def _tick(self):
        self._angle = (self._angle + 2.2 * self._speed) % 360.0
        self.update()

    # ------------------------------------------------------------ 工具
    @staticmethod
    def _find_stage(widget):
        """沿父链找到 LightStage。"""
        from .light_stage import LightStage
        w = widget.parent()
        while w is not None:
            if isinstance(w, LightStage):
                return w
            w = w.parent()
        return None

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, RADIUS, RADIUS)

        if not self._on:
            p.setPen(QPen(QColor("#2c2e33"), 1))
            p.setBrush(QColor("#1e1f24"))
            p.drawRoundedRect(rect, RADIUS, RADIUS)
            p.end()
            return

        # 1) 采样背后的模糊光场 → 毛玻璃底色
        stage = self._find_stage(self)
        bg = stage.bg_pixmap() if stage is not None else None
        if bg is not None:
            tl = stage.mapFromGlobal(self.mapToGlobal(self.rect().topLeft()))
            sx, sy = max(0, tl.x()), max(0, tl.y())
            sw = min(self.width(), bg.width() - sx)
            sh = min(self.height(), bg.height() - sy)
            if sw > 0 and sh > 0:
                src = bg.copy(sx, sy, sw, sh)
                p.save()
                p.setClipPath(path)
                p.drawPixmap(0, 0, src)
                p.restore()

        # 2) 深色蒙版：压暗透出的光，保证文字可读
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(10, 14, 18, self._tint))
        p.drawRoundedRect(rect, RADIUS, RADIUS)

        # 3) 顶部漫反射高光
        hi = QLinearGradient(rect.left(), rect.top(),
                             rect.left(), rect.top() + rect.height() * 0.5)
        hi.setColorAt(0.0, QColor(255, 255, 255, 30))
        hi.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(hi)
        p.drawRoundedRect(rect, RADIUS, RADIUS)

        # 4) 沿轮廓流转的光（柔光外描边 + 亮线内描边）
        center = QPointF(rect.center())
        cg = QConicalGradient(center, self._angle)
        a = lambda v: max(0, min(255, int(v * self._border)))
        cg.setColorAt(0.00, QColor(126, 231, 135, a(0)))
        cg.setColorAt(0.26, QColor(126, 231, 135, a(52)))
        cg.setColorAt(0.40, QColor(26, 188, 156, a(225)))
        cg.setColorAt(0.50, QColor(200, 245, 255, a(185)))
        cg.setColorAt(0.58, QColor(138, 180, 255, a(170)))
        cg.setColorAt(0.70, QColor(26, 188, 156, a(40)))
        cg.setColorAt(1.00, QColor(126, 231, 135, a(0)))

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setOpacity(0.40)
        p.setPen(QPen(QBrush(cg), 4.0))
        p.drawRoundedRect(rect, RADIUS, RADIUS)
        p.setOpacity(1.0)
        p.setPen(QPen(QBrush(cg), 1.6))
        p.drawRoundedRect(rect, RADIUS, RADIUS)

        p.end()
