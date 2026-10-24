# -*- coding: utf-8 -*-
"""
传统模式默认界面
================
布局（对照《传统模式默认界面.pptx》）：
  - 顶部导航栏与 AI 模式完全一致（由主窗口统一提供，按钮变为"进入AI模式"）。
  - 主区域：文本编辑器（可编辑标准源码）+ 底部终端窗口（运行输出）。
  - 右侧功能面板：向AI提问（输入框+发送）、模型接口编辑、模型选择。
  - 运行时代码行高亮：正在执行的代码行以淡黄底色高亮。
"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPlainTextEdit, QPushButton, QFrame,
                             QComboBox, QMessageBox)
from PyQt6.QtCore import pyqtSignal

from .widgets.code_editor import CodeEditor


class TraditionalModePage(QWidget):
    """传统模式页面：编辑器 + 终端 + 右侧 AI 问答面板。"""

    # 信号
    ask_ai = pyqtSignal(str)              # 向 AI 提问（自由问答）
    edit_api = pyqtSignal()               # 模型接口编辑
    model_changed = pyqtSignal(str)       # 模型选择切换

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 8)
        root.setSpacing(8)

        # ---------------- 左侧：编辑器（终端由主窗口底部停靠面板统一提供）
        editor_frame = QFrame(); editor_frame.setProperty("panel", True)
        ef = QVBoxLayout(editor_frame)
        title = QLabel("源代码编辑器（可编辑）")
        title.setStyleSheet("font-weight: bold; color: #1abc9c;")
        self.code_edit = CodeEditor("python")
        ef.addWidget(title)
        ef.addWidget(self.code_edit, 1)
        root.addWidget(editor_frame, 1)

        # ---------------- 右侧：AI 功能面板
        panel = QFrame(); panel.setProperty("panel", True)
        panel.setFixedWidth(260)
        pl = QVBoxLayout(panel)

        ptitle = QLabel("AI 助手")
        ptitle.setStyleSheet("font-weight: bold; color: #74b9ff;")
        pl.addWidget(ptitle)

        # 向AI提问
        self.ask_edit = QPlainTextEdit()
        self.ask_edit.setPlaceholderText("向AI提问……")
        self.btn_ask = QPushButton("发送提问")
        self.btn_ask.setProperty("primary", True)
        pl.addWidget(QLabel("向AI提问"))
        pl.addWidget(self.ask_edit, 1)
        pl.addWidget(self.btn_ask)

        # 模型选择
        pl.addWidget(QLabel("模型选择"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        pl.addWidget(self.model_combo)

        # 模型接口编辑
        self.btn_api = QPushButton("模型接口编辑")
        pl.addWidget(self.btn_api)
        pl.addStretch(1)

        root.addWidget(panel)

        # 信号连接
        self.btn_ask.clicked.connect(self._on_ask)
        self.btn_api.clicked.connect(self.edit_api.emit)
        self.model_combo.currentTextChanged.connect(self.model_changed.emit)

    # ------------------------------------------------------------ 交互
    def _on_ask(self):
        text = self.ask_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请先输入要提问的内容")
            return
        self.ask_ai.emit(text)

    # ------------------------------------------------------------ 数据接口
    def set_models(self, models: list[str], current: str):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)

    def set_code(self, code: str):
        self.code_edit.setPlainText(code)

    def code(self) -> str:
        return self.code_edit.toPlainText()

    def set_language(self, language: str):
        self.code_edit.set_language(language)

    def highlight_line(self, line: int):
        self.code_edit.highlight_exec_line(line)
