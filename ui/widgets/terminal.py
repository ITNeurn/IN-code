# -*- coding: utf-8 -*-
"""
终端面板组件
============
显示程序运行输出日志。深色风格，只读，支持清空。
"""
from PyQt6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtGui import QTextCursor


class TerminalPanel(QWidget):
    """终端窗口：输出日志 + 清空按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        title = QLabel("终端")
        title.setStyleSheet("font-weight: bold;")
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
