# -*- coding: utf-8 -*-
"""沉浸光感
==========
在窗口边缘绘制缓慢呼吸的青绿 / 冷蓝 / 薄荷极光光晕，营造"屏幕在发光"的
沉浸氛围（参考华为 HarmonyOS 的沉浸光感效果）。

实现要点：
  - 作为主窗口的透明子控件覆盖整窗，仅填充四周淡渐变，中部保持透明；
  - 设置 WA_TransparentForMouseEvents，完全不拦截鼠标操作；
  - 50ms 定时器推进相位，让光晕位置轻微漂移，形成呼吸感。
"""
import math

from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QRadialGradient
from PyQt6.QtWidgets import QWidget


class AmbientGlow(QWidget):
    """窗口边缘的呼吸极光层。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ 开关
    def start(self):
        self.show()
        self.raise_()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    # ------------------------------------------------------------ 动画
    def _tick(self):
        self._phase = (self._phase + 0.010) % (2 * math.pi)
        self.update()

    # ------------------------------------------------------------ 绘制
    @staticmethod
    def _aura(p: QPainter, cx: float, cy: float, radius: float,
              color: str, alpha: int):
        """在 (cx, cy) 处铺一层径向渐隐光晕。"""
        g = QRadialGradient(QPointF(cx, cy), radius)
        c0 = QColor(color)
        c0.setAlpha(alpha)
        c_mid = QColor(color)
        c_mid.setAlpha(int(alpha * 0.35))
        c1 = QColor(color)
        c1.setAlpha(0)
        g.setColorAt(0.0, c0)
        g.setColorAt(0.55, c_mid)
        g.setColorAt(1.0, c1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

    def paintEvent(self, event):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._phase
        # 顶部青绿极光（左右微摆）
        self._aura(p, w * (0.5 + 0.05 * math.sin(t)), -h * 0.22,
                   max(w, h) * 0.58, "#1abc9c", 56)
        # 左上冷蓝辅助光
        self._aura(p, -w * 0.08 + math.sin(t + 1.2) * 26, h * 0.12,
                   w * 0.5, "#4a7dff", 38)
        # 右下薄荷余晖
        self._aura(p, w * 1.06, h * (0.96 + 0.03 * math.cos(t)), w * 0.48,
                   "#7ee787", 30)
        p.end()
