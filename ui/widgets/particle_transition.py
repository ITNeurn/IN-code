# -*- coding: utf-8 -*-
"""粒子转场：消散 / 拼接
========================
AI 模式 <-> 传统模式 切换时，当前页面碎裂成粒子向外飞散（消散），
新页面的粒子从四周汇聚拼回原位（拼接）。

实现：把页面快照切成网格碎片（每片是一小块 QPixmap），
用单一 QTimer 驱动所有碎片的位置/旋转/透明度，避免上百个 QPropertyAnimation。
"""
import math
import random

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import QWidget


class ParticleTransition(QWidget):
    """覆盖在页面栈上的粒子转场层。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._particles = []
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._t = 0.0
        self._duration = 0.0
        self._callback = None
        self._mode = "dissolve"  # dissolve | assemble
        self.hide()

    # ------------------------------------------------------------ 公共接口
    def dissolve(self, pixmap: QPixmap, on_finished=None):
        """当前页碎裂成粒子向外飞散。"""
        self._mode = "dissolve"
        self._build_particles(pixmap, scatter=True)
        self._duration = 0.55
        self._t = 0.0
        self._callback = on_finished
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self._timer.start()

    def assemble(self, pixmap: QPixmap, on_finished=None):
        """粒子从四周汇聚拼成新页。"""
        self._mode = "assemble"
        self._build_particles(pixmap, scatter=False)
        self._duration = 0.60
        self._t = 0.0
        self._callback = on_finished
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self._timer.start()

    # ------------------------------------------------------------ 粒子构建
    def _build_particles(self, pixmap: QPixmap, scatter: bool):
        self._particles = []
        w, h = pixmap.width(), pixmap.height()
        if w <= 0 or h <= 0:
            return
        # 网格粒度：宽 14 列，高按比例
        cols = 14
        rows = max(6, int(h / (w / cols)))
        cw, ch = w / cols, h / rows
        rnd = random.Random(20261106)

        for r in range(rows):
            for c in range(cols):
                sx, sy = c * cw, r * ch
                sw = min(cw + 1, w - sx)
                sh = min(ch + 1, h - sy)
                tile = pixmap.copy(int(sx), int(sy), int(sw), int(sh))

                # 目标（原位）与起点
                tx, ty = sx, sy
                if scatter:
                    # 消散：从原位向外飞到远处
                    angle = math.atan2(ty - h / 2, tx - w / 2) + rnd.uniform(-0.6, 0.6)
                    dist = rnd.uniform(260, 620)
                    start_x, start_y = tx, ty
                    end_x = tx + math.cos(angle) * dist
                    end_y = ty + math.sin(angle) * dist
                else:
                    # 拼接：从远处飞回原位
                    angle = rnd.uniform(0, 6.283)
                    dist = rnd.uniform(280, 640)
                    start_x = tx + math.cos(angle) * dist
                    start_y = ty + math.sin(angle) * dist
                    end_x, end_y = tx, ty

                self._particles.append({
                    "tile": tile,
                    "sx": start_x, "sy": start_y,
                    "ex": end_x, "ey": end_y,
                    "rot0": rnd.uniform(-180, 180),
                    "rot1": rnd.uniform(-90, 90),
                    "delay": rnd.uniform(0.0, 0.18),
                    "w": sw, "h": sh,
                })

    # ------------------------------------------------------------ 动画
    def _tick(self):
        self._t += 0.016
        if self._t >= self._duration:
            self._timer.stop()
            self._particles = []
            self.hide()
            if self._callback:
                cb = self._callback
                self._callback = None
                cb()
            return
        self.update()

    @staticmethod
    def _ease_out_cubic(t: float) -> float:
        return 1.0 - (1.0 - t) ** 3

    @staticmethod
    def _ease_in_cubic(t: float) -> float:
        return t ** 3

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for pt in self._particles:
            raw = (self._t - pt["delay"]) / (self._duration - pt["delay"])
            raw = max(0.0, min(1.0, raw))
            if self._mode == "dissolve":
                e = self._ease_in_cubic(raw)
                x = pt["sx"] + (pt["ex"] - pt["sx"]) * e
                y = pt["sy"] + (pt["ey"] - pt["sy"]) * e
                rot = pt["rot0"] + (pt["rot1"] - pt["rot0"]) * e
                opacity = 1.0 - e
            else:
                e = self._ease_out_cubic(raw)
                x = pt["sx"] + (pt["ex"] - pt["sx"]) * e
                y = pt["sy"] + (pt["ey"] - pt["sy"]) * e
                rot = pt["rot0"] + (0 - pt["rot0"]) * e
                opacity = e

            p.save()
            p.setOpacity(opacity)
            t = QTransform()
            t.translate(x + pt["w"] / 2, y + pt["h"] / 2)
            t.rotate(rot)
            t.translate(-pt["w"] / 2, -pt["h"] / 2)
            p.setTransform(t, True)
            p.drawPixmap(0, 0, pt["tile"])
            p.restore()
        p.end()
