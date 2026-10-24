# -*- coding: utf-8 -*-
"""
AI 模式默认界面
===============
按用户要求：整个工作区只有一块放大的自然语言描述编辑区。
  - 无"分区1/分区2"标题、无提示文字、无 AI 代码区、无终端。
  - AI 生成代码保存在内部属性中（不在 AI 模式展示），
    切换到传统模式时同步进源码编辑器对照查看。
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QFrame


class AIModePage(QWidget):
    """AI 模式页面：单一大尺寸自然语言编辑区。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 8)

        panel = QFrame(); panel.setProperty("panel", True)
        pl = QVBoxLayout(panel)

        # 唯一工作区：自然语言流程描述（无提示文字，占满）
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setStyleSheet("border: none; font-size: 14px;")
        pl.addWidget(self.desc_edit)
        layout.addWidget(panel, 1)

        # AI 生成代码内部存放（AI 模式不展示，传统模式对照查看）
        self._code = ""
        self._language = "python"

    # ------------------------------------------------------------ 数据接口
    def description(self) -> str:
        return self.desc_edit.toPlainText().strip()

    def set_description(self, text: str):
        self.desc_edit.setPlainText(text)

    def set_code(self, code: str):
        self._code = code

    def code(self) -> str:
        return self._code

    def set_language(self, language: str):
        self._language = language
