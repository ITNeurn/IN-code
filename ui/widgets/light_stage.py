# -*- coding: utf-8 -*-
"""沉浸光感 - 背景光场（毛玻璃底层）
====================================
参考华为 HarmonyOS 沉浸光感规范：
  沉浸式系统材质 = 组件背后的内容被真实模糊后透出，形成通透的毛玻璃质感。

实现要点：
  1. 光场先以 1/4 分辨率渲染，再做重度高斯模糊，放大铺满——得到天然柔光背景。
  2. 把模糊后的全尺寸背景缓存为 _bg_pixmap，供上层 LightPanel 采样。
  3. LightPanel 直接拷贝背后的模糊光场 + 深色蒙版 = 真正的毛玻璃，而不是纯色半透明。
"""
import math
import random

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (QPainter, QColor, QRadialGradient, QPixmap, QImage)
from PyQt6.QtWidgets import QWidget, QGraphicsScene, QGraphicsPixmapItem
from PyQt6.QtWidgets import QGraphicsBlurEffect

LEVELS = {
    "weak":    {"aurora": 0.55, "blur": 14, "dust": 0},
    "balanced": {"aurora": 1.0,  "blur": 22, "dust": 0},
    "strong":  {"aurora": 1.45, "blur": 30, "dust": 46},
}


class LightStage(QWidget):
    """窗口背景光场；同时提供已模糊的背景供面板做毛玻璃采样。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stage")
        self._enabled = False
        self._aurora = 1.0
        self._blur_radius = 22
        self._dust_count = 0
        self._t = 0.0
        self._frame = 0
        self._bg_pixmap: QPixmap | None = None

        rnd = random.Random(20261106)
        self._dust = [(rnd.random(), rnd.random(), rnd.uniform(0.7, 1.9),
                       rnd.uniform(0.0016, 0.0052), rnd.uniform(0, 6.28),
                       rnd.choice(("#7ee787", "#1abc9c", "#8ab4ff")))
                      for _ in range(46)]
        # 粒子发光 sprite（按颜色预生成，绘制时只做 drawPixmap，避免每帧建渐变）
        self._sprites = {c: self._make_sprite(c)
                         for c in ("#7ee787", "#1abc9c", "#8ab4ff")}

        self._timer = QTimer(self)
        self._timer.setInterval(45)
        self._timer.timeout.connect(self._tick)

        # 模糊缓存：复用场景，避免每帧重建
        self._blur_scene = QGraphicsScene()
        self._blur_item = QGraphicsPixmapItem()
        self._blur_effect = QGraphicsBlurEffect()
        self._blur_effect.setBlurRadius(self._blur_radius)
        self._blur_item.setGraphicsEffect(self._blur_effect)
        self._blur_scene.addItem(self._blur_item)

    @staticmethod
    def _make_sprite(color: str) -> QPixmap:
        """生成一颗柔和发光粒子的贴图（64×64）。"""
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        g = QRadialGradient(QPointF(32, 32), 32)
        c0 = QColor(color); c0.setAlpha(220)
        c1 = QColor(color); c1.setAlpha(0)
        g.setColorAt(0.0, c0)
        g.setColorAt(0.35, QColor(color).lighter(115))
        g.setColorAt(1.0, c1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(32, 32), 32, 32)
        p.end()
        return pm

    def resizeEvent(self, event):
        # 尺寸变化后旧缓存尺寸不匹配，标记重渲
        self._bg_pixmap = None
        super().resizeEvent(event)

    # ------------------------------------------------------------ 开关
    def set_effect(self, enabled: bool, level: str = "balanced"):
        cfg = LEVELS.get(level, LEVELS["balanced"])
        self._enabled = bool(enabled)
        self._aurora = cfg["aurora"]
        self._blur_radius = cfg["blur"]
        self._blur_effect.setBlurRadius(self._blur_radius)
        self._dust_count = cfg["dust"]
        self._bg_pixmap = None
        if self._enabled:
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
        self.update()

    def bg_pixmap(self) -> QPixmap | None:
        """供 LightPanel 采样的已模糊背景。"""
        return self._bg_pixmap

    def _tick(self):
        self._t += 0.045
        self._frame += 1
        # 模糊背景每 5 帧（约 225ms）重渲一次即可——光晕漂移很慢，肉眼无感；
        # CPU 高斯模糊是主线程大户，降频后界面不再被光场拖住。
        if self._frame % 5 == 0 or self._bg_pixmap is None:
            self._render_bg()
        self.update()

    # ------------------------------------------------------------ 渲染
    @staticmethod
    def _aura(p: QPainter, cx: float, cy: float, radius: float,
              color: str, alpha: int):
        g = QRadialGradient(QPointF(cx, cy), radius)
        alpha = max(0, min(255, int(alpha)))
        c0 = QColor(color); c0.setAlpha(alpha)
        c_mid = QColor(color); c_mid.setAlpha(int(alpha * 0.34))
        c1 = QColor(color); c1.setAlpha(0)
        g.setColorAt(0.0, c0)
        g.setColorAt(0.5, c_mid)
        g.setColorAt(1.0, c1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

    def _render_bg(self):
        """把光场渲染到小尺寸缓冲 → 模糊 → 放大缓存为 _bg_pixmap。"""
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        scale = 4
        sw, sh = max(1, w // scale), max(1, h // scale)

        buf = QPixmap(sw, sh)
        buf.fill(QColor("#000000"))
        p = QPainter(buf)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self._t
        k = self._aurora

        # 在小画布上画光晕（坐标按缩放换算）
        self._aura(p, sw * (0.5 + 0.04 * math.sin(t * 0.5)), -sh * 0.10,
                   max(sw, sh) * 0.95, "#1abc9c", int(205 * k))
        self._aura(p, -sw * 0.08 + math.sin(t * 0.7 + 1.2) * 30 / scale, sh * 0.10,
                   sw * 0.75, "#3d6bff", int(180 * k))
        self._aura(p, sw * 1.02, sh * (0.95 + 0.03 * math.cos(t * 0.6)),
                   sw * 0.75, "#7ee787", int(150 * k))
        self._aura(p, sw * (0.42 + 0.05 * math.cos(t * 0.4)),
                   sh * (0.52 + 0.05 * math.sin(t * 0.45)),
                   max(sw, sh) * 0.72, "#14b8a6", int(130 * k))
        self._aura(p, sw * (0.85 + 0.02 * math.sin(t * 0.35)), sh * 0.45,
                   sw * 0.55, "#4a7dff", int(100 * k))
        if k > 1.2:
            self._aura(p, sw * 0.35, sh * 1.05, sw * 0.80, "#1abc9c",
                       int(130 * k))
        p.end()

        # 重度模糊
        self._blur_item.setPixmap(buf)
        blurred = QPixmap(sw, sh)
        blurred.fill(Qt.GlobalColor.black)
        pp = QPainter(blurred)
        self._blur_scene.render(pp, QRectF(0, 0, sw, sh),
                                QRectF(0, 0, sw, sh))
        pp.end()

        # 放大到全尺寸缓存（平滑缩放 = 进一步柔化）
        self._bg_pixmap = blurred.scaled(
            w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

    def paintEvent(self, event):
        p = QPainter(self)
        if not self._enabled or self._bg_pixmap is None:
            p.fillRect(self.rect(), QColor("#000000"))
            p.end()
            return
        p.drawPixmap(0, 0, self._bg_pixmap)

        # 粒子（强档）：直接画预生成的发光 sprite，成本极低，每帧流畅移动
        if self._dust_count:
            w, h = self.width(), self.height()
            t = self._t
            for i in range(self._dust_count):
                nx, ny, r, spd, phase, color = self._dust[i]
                y = (ny - t * spd) % 1.0
                x = (nx + 0.012 * math.sin(t * 0.9 + phase)) % 1.0
                twinkle = 0.55 + 0.45 * math.sin(t * 1.7 + phase)
                size = 10 + r * 8
                p.setOpacity(0.75 * twinkle)
                p.drawPixmap(int(x * w - size / 2), int(y * h - size / 2),
                             int(size), int(size), self._sprites[color])
            p.setOpacity(1.0)
        p.end()
