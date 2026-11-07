# -*- coding: utf-8 -*-
"""
终端面板组件
============
显示程序运行输出日志。深色风格，只读，支持清空。
沉浸光感开启时，终端面板采样光场背景做毛玻璃。
"""
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel


class TerminalPanel(QWidget):
    """终端窗口：输出日志 + 清空按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("terminalRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        title = QLabel("终端")
        title.setStyleSheet("font-weight: bold; color:#7ee787;")
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setFixedWidth(64)
        bar.addWidget(title)
        bar.addStretch(1)
        bar.addWidget(self.btn_clear)
        layout.addLayout(bar)

        self.output = QPlainTextEdit()
        self.output.setProperty("terminal", True)
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)

        self.btn_clear.clicked.connect(self.clear)

    # ------------------------------------------------------------ 毛玻璃背景
    @staticmethod
    def _find_stage(widget):
        from .light_stage import LightStage
        w = widget.parent()
        while w is not None:
            if isinstance(w, LightStage):
                return w
            w = w.parent()
        return None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

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
        # 深色蒙版
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 12, 15, 130))
        p.drawRoundedRect(rect, 10, 10)
        p.end()

    # ------------------------------------------------------------ 输出
    def append(self, text: str):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def append_line(self, text: str):
        self.append(text.rstrip("\n") + "\n")

    def clear(self):
        self.output.clear()

