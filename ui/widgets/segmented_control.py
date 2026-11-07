# -*- coding: utf-8 -*-
"""分段控件：带滑动高亮动画
============================
替代 QSS :checked 直接跳变的方案。选中块（胶囊）用 QPropertyAnimation
在 280ms 内平滑滑动到目标分段，OutCubic 缓动，手感自然。
"""
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRectF, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget


class SegmentedControl(QWidget):
    """三段式分段控件，选中块平滑滑动。"""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self._items = list(items)
        self._selected = 0
        self._ind_x = 0.0
        self._ind_w = 0.0
        self.setMinimumHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"indicatorX", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda _: self.update())

        self._selected_changed = None

    # ------------------------------------------------------------ 属性
    @pyqtProperty(float)
    def indicatorX(self):
        return self._ind_x

    @indicatorX.setter
    def indicatorX(self, v):
        self._ind_x = v

    # ------------------------------------------------------------ 接口
    def set_on_change(self, cb):
        self._selected_changed = cb

    def select(self, index: int):
        if index == self._selected:
            return
        self._selected = index
        self._animate_to(index)
        if self._selected_changed:
            self._selected_changed(self._items[index][0])

    def set_selected_key(self, key: str):
        for i, (k, _) in enumerate(self._items):
            if k == key:
                self._selected = i
                self._ind_x = i * self._seg_w()
                self._ind_w = self._seg_w()
                self.update()
                return

    def current_index(self) -> int:
        return self._selected

    def current_key(self) -> str:
        return self._items[self._selected][0]

    # ------------------------------------------------------------ 几何
    def _seg_w(self) -> float:
        n = len(self._items)
        return (self.width() - 8) / n if n else 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._ind_w = self._seg_w()
        self._ind_x = 4 + self._selected * self._seg_w()

    # ------------------------------------------------------------ 动画
    def _animate_to(self, index: int):
        target = 4 + index * self._seg_w()
        self._anim.stop()
        self._anim.setStartValue(self._ind_x)
        self._anim.setEndValue(target)
        self._anim.start()

    # ------------------------------------------------------------ 交互
    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        sw = self._seg_w()
        idx = int((event.position().x() - 4) // sw)
        idx = max(0, min(len(self._items) - 1, idx))
        self.select(idx)

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = QRectF(0, 0, w, h).adjusted(0.5, 0.5, -0.5, -0.5)

        # 背景轨道
        p.setPen(QColor("#24272e"))
        p.setBrush(QColor("#1a1d22"))
        p.drawRoundedRect(r, 11, 11)

        # 滑动选中块
        self._ind_w = self._seg_w()
        if self._ind_w > 0:
            ind = QRectF(self._ind_x, 4, self._ind_w, h - 8)
            p.setPen(Qt.PenStyle.NoPen)
            grad = QColor("#1abc9c")
            p.setBrush(QColor("#2b3038"))
            p.drawRoundedRect(ind, 8, 8)
            # 选中块顶部青绿高光线
            p.setPen(QColor(26, 188, 156, 160))
            p.drawLine(int(ind.left() + 6), int(ind.top() + 1),
                       int(ind.right() - 6), int(ind.top() + 1))

        # 文字
        p.setPen(QColor("#0b0c0e"))
        font = QFont("Microsoft YaHei", 10)
        font.setBold(True)
        p.setFont(font)
        sw = self._seg_w()
        for i, (_, text) in enumerate(self._items):
            cx = 4 + i * sw + sw / 2
            if i == self._selected:
                continue  # 选中文字用粗体白，后面单独画
            p.setPen(QColor("#8b949e"))
            f = QFont("Microsoft YaHei", 10)
            p.setFont(f)
            p.drawText(QRectF(4 + i * sw, 0, sw, h),
                       Qt.AlignmentFlag.AlignCenter, text)

        # 选中项文字
        if self._ind_w > 0:
            p.setPen(QColor("#ffffff"))
            p.setFont(font)
            p.drawText(QRectF(self._ind_x, 0, self._ind_w, h),
                       Qt.AlignmentFlag.AlignCenter,
                       self._items[self._selected][1])

        p.end()
