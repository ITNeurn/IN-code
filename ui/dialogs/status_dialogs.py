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


class SuperDownloadDialog(_CardDialog):
    """超能模式下载进度页面：总进度 + MoE 进度 + 详细日志。

    下载在后台线程继续，点击【转到后台运行】可直接关闭本页，不中断下载。
    """

    def __init__(self, total: int, with_moe: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(520, 420)
        self._finished = False

        self.title = self.add_text("超能模式：正在准备离线能力包", size=16)
        self.stage = self.add_text("正在准备隔离环境", size=13, bold=False,
                                   color="#9aa0a6")

        # 总进度条
        self.bar = QProgressBar()
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setFormat("%v / %m")
        self.card_layout.addWidget(self.bar)

        # MoE 进度（仅用户选择安装时显示）
        self.moe_label = None
        self.moe_bar = None
        if with_moe:
            self.moe_label = self.add_text("MoE 模型：等待开始", size=12,
                                           bold=False, color="#9aa0a6")
            self.moe_bar = QProgressBar()
            self.moe_bar.setRange(0, 0)     # 忙碌状态，收到百分比后改为确定值
            self.card_layout.addWidget(self.moe_bar)

        # 详细日志
        self.log_view = QLabel("")
        self.log_view.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.log_view.setWordWrap(True)
        self.log_view.setStyleSheet(
            "font-size:11px;color:#7f868f;background:#1e2024;"
            "border-radius:6px;padding:8px;")
        self.log_view.setMinimumHeight(70)
        self.card_layout.addWidget(self.log_view)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_bg = QPushButton("转到后台运行")
        self.btn_bg.clicked.connect(self._go_background)
        row.addWidget(self.btn_bg)
        row.addStretch(1)
        self.card_layout.addLayout(row)

    # ------------------------------------------------------------ 信号槽
    def set_progress(self, done: int, total: int, text: str):
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(done)
        self.stage.setText(text)

    def set_moe(self, pct: int, text: str):
        if self.moe_bar is None:
            return
        self.moe_label.setText(text)
        if pct < 0:
            self.moe_bar.setRange(0, 0)
        else:
            self.moe_bar.setRange(0, 100)
            self.moe_bar.setValue(pct)

    def append_log(self, text: str):
        # 只保留最近 3 行，避免撑爆弹窗
        lines = (self.log_view.text().splitlines() + [text.strip()])[-3:]
        self.log_view.setText("\n".join(lines))

    def on_finished(self, ok: bool, failed: list):
        self._finished = True
        self.bar.setValue(self.bar.maximum())
        self.stage.setText("全部完成" if ok else "已完成（部分库失败）")
        if failed:
            self.append_log("失败：" + "、".join(failed[:8]))
        self.accept()

    def _go_background(self):
        # 只关闭窗口，不中断后台下载
        self.accept()

    def closeEvent(self, event):
        # 关闭即视为转到后台，绝不再取消下载
        event.accept()


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
