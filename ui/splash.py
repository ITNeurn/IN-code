# -*- coding: utf-8 -*-
"""启动动画：无边框 WebEngine 窗口播放 assets/splash.html，淡出后回调。

防露馅细节：
- 禁用右键菜单 / 文本选择 / 链接拖拽，看起来就是原生窗口
- WebEngine 加载完成前隐藏视图（避免白闪），父窗口底色与动画一致
- 固定 1180×760 居中，与主窗口尺寸一致，切换无位移感
"""
import os
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, QUrl
from PyQt6.QtWidgets import QVBoxLayout, QWidget

SPLASH_DURATION_MS = 5000      # 动画完整播放时长（两幕约 4s，留余量）
FADE_MS = 450                  # 结尾淡出时长


class SplashScreen(QWidget):
    def __init__(self, html_path: str, on_finish):
        super().__init__()
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        self._on_finish = on_finish
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        # 尺寸自适应：正常屏用 1180×760（与主窗口一致），小屏按比例收缩，
        # 避免窗口超出屏幕导致动画被裁切
        from PyQt6.QtGui import QGuiApplication
        scr = QGuiApplication.primaryScreen().availableGeometry()
        w = min(1180, int(scr.width() * 0.88))
        h = min(760, int(scr.height() * 0.85))
        self.setFixedSize(w, h)
        self.setStyleSheet("background: #050607;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web = QWebEngineView(self)
        self.web.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        layout.addWidget(self.web)
        # 不能隐藏视图：隐藏时网页视口为 0×0，Canvas 会初始化成 0 宽。
        # 改用页面底色防白闪（与动画背景同色）
        from PyQt6.QtGui import QColor
        self.web.page().setBackgroundColor(QColor("#050607"))
        self.web.load(QUrl.fromLocalFile(os.path.abspath(html_path)))

        self._center()
        self._faded = False
        # 计时从页面加载完成才开始，避免 Chromium 初始化耗时把动画截断
        self.web.loadFinished.connect(lambda _ok: QTimer.singleShot(
            SPLASH_DURATION_MS, self._fade_out))
        # 兜底：万一加载失败/超时，也不能一直卡在启动动画
        QTimer.singleShot(SPLASH_DURATION_MS + 2500, self._fade_out)

    def _center(self):
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.x() + (screen.width() - self.width()) // 2,
                  screen.y() + (screen.height() - self.height()) // 2)

    def _fade_out(self):
        if self._faded:
            return
        self._faded = True
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(FADE_MS)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.finished.connect(self._finish)
        self._anim.start()

    def _finish(self):
        self.close()
        self._on_finish()
