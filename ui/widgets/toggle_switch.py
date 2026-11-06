# -*- coding: utf-8 -*-
"""胶囊开关（HarmonyOS / 华为风格）
=================================
浅灰轨道 + 白色圆形滑块，开启时轨道变为青绿渐变，滑块带 160ms 缓动滑动。
"""
from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush
from PyQt6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """自绘胶囊开关，用法与 QCheckBox 类似。"""

    toggled = pyqtSignal(bool)

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._knob = 1.0 if checked else 0.0
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ------------------------------------------------------------ 属性
    def _get_knob(self) -> float:
        return self._knob

    def _set_knob(self, v: float):
        self._knob = v
        self.update()

    # 不能用 pos（与 QWidget.pos 冲突），自定义 knob 属性驱动动画
    knob = pyqtProperty(float, fget=_get_knob, fset=_set_knob)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, on: bool):
        on = bool(on)
        if on == self._checked:
            return
        self._checked = on
        self._anim.stop()
        self._anim.setStartValue(self._knob)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    # ------------------------------------------------------------ 交互
    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        # 轨道
        p.setPen(Qt.PenStyle.NoPen)
        if self._checked:
            g = QLinearGradient(0, 0, w, h)
            g.setColorAt(0.0, QColor("#1abc9c"))
            g.setColorAt(1.0, QColor("#23d1ae"))
            p.setBrush(QBrush(g))
        else:
            p.setBrush(QColor("#3a3d44"))
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        # 滑块
        d = h - 6
        x = 3 + self._knob * (w - d - 6)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(QRectF(x, 4, d, d))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, 3, d, d))
        p.end()
