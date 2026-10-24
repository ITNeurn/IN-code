# -*- coding: utf-8 -*-
"""设置 - 超能模式页：激活按钮 / 已开启状态 + 关闭按钮。"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from core.super_mode import SuperModeManager
from ..dialogs.super_mode_wizard import SuperModeWizard


class SuperModePage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.manager = SuperModeManager(settings)
        self.wizard: SuperModeWizard | None = None

        self.lay = QVBoxLayout(self)
        self.lay.setSpacing(14)
        self._build()

    # ------------------------------------------------------------ 界面
    def _build(self):
        # 清空重建（激活后刷新状态）
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self.manager.active:
            status = QLabel("超能模式：已开启")
            status.setStyleSheet("font-size:15px;color:#1abc9c;font-weight:bold;")
            self.lay.addWidget(status)
            btn = QPushButton("关闭超能模式")
            btn.setProperty("danger", True)
            btn.clicked.connect(self._deactivate)
            self.lay.addWidget(btn)
        else:
            btn = QPushButton("点这里激活超能模式")
            btn.setProperty("primary", True)
            btn.setStyleSheet("font-size:15px;padding:10px 24px;")
            btn.clicked.connect(self._activate)
            self.lay.addWidget(btn)
        self.lay.addStretch(1)

    # ------------------------------------------------------------ 交互
    def _activate(self):
        # 启动向导：三重警告 → 目录选择 → MoE 选择 → 完成页（后台下载）
        self.wizard = SuperModeWizard(self.settings, self)
        self.wizard.run()
        self._build()   # 无论成功与否都刷新状态

    def _deactivate(self):
        self.manager.deactivate()
        self._build()
