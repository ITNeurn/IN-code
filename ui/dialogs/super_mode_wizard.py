# -*- coding: utf-8 -*-
"""
超能模式激活向导
================
严格按需求顺序弹窗跳转（对应 6 张 PPT）：
  1. 第一警告页：⚠️确定激活超能模式吗？⚠️        [确认激活 / 取消激活]
  2. 第二警告页：⚠️确定激活超能模式将允许部署MoE…⚠️ [确认激活 / 取消激活]
  3. 最后警告页：⚠️这是最后一次询问…⚠️           [确认激活 / 取消激活]
  4. 库安装目录选择页："请选择库安装目录" + 磁盘路径选择框 + [确认]
  5. MoE 模型选择页："库将开始后台安装，是否安装-deepseek R1 MoE？"
     小字备注：MoE模型体积很大，如果硬盘空间紧张建议选否。  [是 / 否]
  6. 配置完成页："超能模式所需组件正在安装，可以返回了" + [返回设置]
     （进入准备动画 MP4 在后台下载启动前播放一次）
任何一步取消都会终止整个激活流程。
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QLineEdit, QFileDialog, QFrame,
                             QMessageBox, QWidget)

from config.settings import ASSETS_DIR
from core.super_mode import SuperModeManager, SuperDownloadWorker

# 尝试加载视频组件（PyQt6-Multimedia 不可用时优雅降级为静态文字）
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    HAS_VIDEO = True
except Exception:
    HAS_VIDEO = False


class _WizardDialog(QDialog):
    """向导基类：模态、居中卡片。"""

    def __init__(self, parent=None, width=620, height=260):
        super().__init__(parent)
        self.setModal(True)
        self.setFixedSize(width, height)
        self.setWindowTitle("超能模式")
        card = QFrame(self)
        card.setProperty("panel", True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(30, 26, 30, 26)
        lay.setSpacing(16)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        self.lay = lay

    def add_label(self, text, size=14, bold=True, color="#e8eaed"):
        lab = QLabel(text)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setWordWrap(True)
        lab.setStyleSheet(f"font-size:{size}px;font-weight:{'bold' if bold else 'normal'};color:{color};")
        self.lay.addWidget(lab)
        return lab

    def add_confirm_cancel(self, ok_text="确认激活", cancel_text="取消激活"):
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton(cancel_text)
        btn_ok = QPushButton(ok_text)
        btn_ok.setProperty("danger", True)   # 警告类确认按钮用醒目红色
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.accept)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        row.addStretch(1)
        self.lay.addLayout(row)


class WarningDialog1(_WizardDialog):
    """第一警告页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_label("⚠️ 确定激活超能模式吗？⚠️", size=16)
        self.lay.addStretch(1)
        self.add_confirm_cancel()


class WarningDialog2(_WizardDialog):
    """第二警告页：说明 MoE / 大参数模型 / 上百个第三方库 / 大量空间。"""

    def __init__(self, parent=None):
        super().__init__(parent, height=300)
        self.add_label(
            "⚠️ 确定激活超能模式将允许部署 MoE 以及大参数模型，将拥有顶级本地能力，"
            "软件将后台下载上百个 Python 环境的第三方库，将占用大量空间 ⚠️", size=14)
        self.lay.addStretch(1)
        self.add_confirm_cancel()


class WarningDialog3(_WizardDialog):
    """最后警告页。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_label("⚠️ 这是最后一次询问，确定激活超能模式吗？⚠️", size=16)
        self.lay.addStretch(1)
        self.add_confirm_cancel()


class LibDirDialog(_WizardDialog):
    """库安装目录选择页。"""

    def __init__(self, parent=None, default_dir=""):
        super().__init__(parent)
        self.add_label("请选择库安装目录", size=16)
        row = QHBoxLayout()
        row.addWidget(QLabel("💾 ："))
        self.edit = QLineEdit(default_dir)
        btn = QPushButton("浏览…")
        btn.clicked.connect(self._browse)
        row.addWidget(self.edit, 1)
        row.addWidget(btn)
        self.lay.addLayout(row)
        self.lay.addStretch(1)
        row2 = QHBoxLayout()
        row2.addStretch(1)
        btn_ok = QPushButton("确认")
        btn_ok.setProperty("primary", True)
        btn_ok.clicked.connect(self.accept)
        row2.addWidget(btn_ok)
        row2.addStretch(1)
        self.lay.addLayout(row2)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "请选择库安装目录", self.edit.text())
        if d:
            self.edit.setText(d)

    def selected_dir(self) -> str:
        return self.edit.text().strip()


class MoeChoiceDialog(_WizardDialog):
    """MoE 模型选择页：是 / 否 两个大按钮。"""

    def __init__(self, parent=None):
        super().__init__(parent, height=300)
        self.choice = False
        self.add_label("库将开始后台安装，是否安装-deepseek R1 MoE？", size=15)
        self.add_label("（MoE模型体积很大，如果硬盘空间紧张建议选否）",
                       size=11, bold=False, color="#9aa0a8")
        self.lay.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        btn_no = QPushButton("否")
        btn_yes = QPushButton("是")
        for b in (btn_no, btn_yes):
            b.setFixedSize(110, 72)
            b.setStyleSheet("font-size:24px;font-weight:bold;")
        btn_yes.setProperty("primary", True)
        btn_no.clicked.connect(self._choose_no)
        btn_yes.clicked.connect(self._choose_yes)
        row.addWidget(btn_no)
        row.addSpacing(24)
        row.addWidget(btn_yes)
        row.addStretch(1)
        self.lay.addLayout(row)

    def _choose_yes(self):
        self.choice = True
        self.accept()

    def _choose_no(self):
        self.choice = False
        self.accept()


class FinishDialog(_WizardDialog):
    """配置完成页：后台下载已启动，可返回设置。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_label("超能模式所需组件正在安装，可以返回了", size=15)
        self.lay.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        btn = QPushButton("返回设置")
        btn.setProperty("primary", True)
        btn.clicked.connect(self.accept)
        row.addWidget(btn)
        row.addStretch(1)
        self.lay.addLayout(row)


class IntroVideoDialog(QDialog):
    """超能模式进入准备动画：播放内置 MP4，播完自动关闭（可点击跳过）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setFixedSize(640, 380)
        self.setWindowTitle("超能模式启动中")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        video_path = ASSETS_DIR / "super_mode_intro.mp4"
        if HAS_VIDEO and video_path.exists():
            self._video = QVideoWidget()
            lay.addWidget(self._video)
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self)
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(self._video)
            self._player.setSource(QUrl.fromLocalFile(str(video_path)))
            self._player.mediaStatusChanged.connect(self._on_status)
            self._player.play()
        else:
            # 无视频组件时降级为动画感文字
            lab = QLabel("⚡ 超能模式正在启动 ⚡")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet("font-size:22px;font-weight:bold;color:#74b9ff;")
            lay.addWidget(lab)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, self.accept)

    def _on_status(self, status):
        if HAS_VIDEO and status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.accept()

    def mousePressEvent(self, event):
        self.accept()    # 点击跳过动画


class SuperModeWizard:
    """超能模式激活向导调度器：严格按 1→2→3→4→5→6 顺序执行。"""

    def __init__(self, settings, parent: QWidget = None):
        self.settings = settings
        self.parent = parent
        self.manager = SuperModeManager(settings)
        self.worker: SuperDownloadWorker | None = None

    def run(self) -> bool:
        """执行完整激活流程。返回是否完成激活（取消返回 False）。"""
        p = self.parent
        # 1~3：三重警告
        for cls in (WarningDialog1, WarningDialog2, WarningDialog3):
            if cls(p).exec() != QDialog.DialogCode.Accepted:
                return False

        # 4：库安装目录
        default_dir = str(Path.home() / ".incode" / "super_libs")
        dlg_dir = LibDirDialog(p, default_dir)
        if dlg_dir.exec() != QDialog.DialogCode.Accepted:
            return False
        lib_dir = dlg_dir.selected_dir()
        if not lib_dir:
            QMessageBox.warning(p, "提示", "请选择有效的库安装目录")
            return False
        try:
            Path(lib_dir).mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            QMessageBox.critical(p, "错误", "没有写入权限或路径无效，无法创建目录")
            return False

        # 5：MoE 选择
        dlg_moe = MoeChoiceDialog(p)
        dlg_moe.exec()
        want_moe = dlg_moe.choice

        # 磁盘空间检查（异常流程：空间不足则弹窗并终止）
        ok, msg = SuperModeManager.check_disk_space(lib_dir, want_moe)
        if not ok:
            QMessageBox.critical(p, "磁盘空间不足", msg)
            return False

        # 进入准备动画
        IntroVideoDialog(p).exec()

        # 写入状态并启动后台下载（不阻塞界面）
        self.manager.activate(lib_dir, want_moe)
        self.worker = SuperDownloadWorker(self.settings, p)
        self.worker.start()

        # 6：配置完成页
        FinishDialog(p).exec()
        return True
