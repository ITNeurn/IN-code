# -*- coding: utf-8 -*-
"""
状态弹窗页面（业务流程弹出窗口）
==============================
对照 PPT 模板，三个弹窗均为居中圆角卡片：
  1. CompileDialog            编译页面："开始理解并编写、编译"
  2. LibraryInstallDialog     库安装模板页面："正在安装所需库（库名）"
  3. UnderstandFailureDialog  理解故障模板页面：标题"理解故障" + 原因 +【返回修改描述】
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QProgressBar,
                             QPushButton, QFrame, QHBoxLayout)


class _CardDialog(QDialog):
    """圆角卡片弹窗基类：无边框、模态、居中内容。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setFixedSize(460, 260)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        card = QFrame(self)
        card.setProperty("panel", True)
        card.setStyleSheet("QFrame{border-radius:14px;background:#26282e;"
                           "border:1px solid #3a3d44;}")
        self.card_layout = QVBoxLayout(card)
        self.card_layout.setContentsMargins(28, 24, 28, 24)
        self.card_layout.setSpacing(14)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

    def add_text(self, text: str, size=15, bold=True, color="#e8eaed") -> QLabel:
        lab = QLabel(text)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setWordWrap(True)
        lab.setStyleSheet(f"font-size:{size}px;color:{color};"
                          f"font-weight:{'bold' if bold else 'normal'};")
        self.card_layout.addWidget(lab)
        return lab


class CompileDialog(_CardDialog):
    """编译页面：AI 解析需求、生成代码、调用编译器时显示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = self.add_text("开始理解并编写、编译", size=16)
        bar = QProgressBar()
        bar.setRange(0, 0)          # 忙碌状态
        self.card_layout.addWidget(bar)

    def set_stage(self, text: str):
        """更新阶段提示（如：AI解析中 / 生成代码 / 编译运行）。"""
        self.label.setText(text)


class LibraryInstallDialog(_CardDialog):
    """库安装模板页面：文字"正在安装所需库（库名）"，括号动态更新。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = self.add_text("正在安装所需库（）", size=15)
        bar = QProgressBar()
        bar.setRange(0, 0)
        self.card_layout.addWidget(bar)

    def set_package(self, name: str):
        self.label.setText(f"正在安装所需库（{name}）")


class UnderstandFailureDialog(_CardDialog):
    """理解故障模板页面：显示无法理解点，并提供【返回修改描述】。"""

    def __init__(self, reason: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(480, 300)
        self.add_text("理解故障", size=18)
        self.add_text(f"无法理解点：（{reason}）", size=13, bold=False, color="#ff6b6b")
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_back = QPushButton("返回修改描述")
        self.btn_back.setProperty("primary", True)
        self.btn_back.clicked.connect(self.accept)
        row.addWidget(self.btn_back)
        row.addStretch(1)
        self.card_layout.addLayout(row)
