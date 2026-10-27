# -*- coding: utf-8 -*-
"""设置 - 本地模型管理页：显示当前选中本地模型 Deepseek R1 7B，可浏览/下载/切换/删除 Ollama 模型。"""
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QListWidget, QInputDialog,
                             QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal

from core.ai_client import list_ollama_models


class _ListWorker(QThread):
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def run(self):
        try:
            self.done.emit(list_ollama_models(self.settings))
        except Exception as e:
            self.error.emit(str(e))


class LocalModelPage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        # 当前生效状态（哪个模式、哪个后端、哪个模型，一目了然）
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-weight:bold; padding:6px;")
        self._refresh_status()
        lay.addWidget(self.status_label)

        # 模式切换：云端 / 内嵌本地模型（点击立即生效）
        row0 = QHBoxLayout()
        b_cloud = QPushButton("使用云端 API")
        b_cloud.clicked.connect(self._use_cloud)
        b_embedded = QPushButton("使用内嵌模型（DeepSeek R1 7B）")
        b_embedded.clicked.connect(self._use_embedded)
        row0.addWidget(b_cloud)
        row0.addWidget(b_embedded)
        row0.addStretch(1)
        lay.addLayout(row0)

        # 内嵌模型文件/引擎就绪状态
        from core.local_engine import find_model, find_server
        gguf = find_model(self.settings)
        engine = find_server()
        status = QLabel(
            f"内嵌模型：{'已就绪 ' + gguf.name if gguf else '缺失'} ｜ "
            f"内嵌引擎：{'已就绪' if engine else '缺失'}")
        status.setStyleSheet("color:#1abc9c;" if (gguf and engine) else "color:#e74c3c;")
        lay.addWidget(status)

        lay.addWidget(QLabel("或选用本机 Ollama 已安装的模型（点击即生效）："))
        self.list = QListWidget()
        self.list.itemClicked.connect(self._select)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        for text, fn in (("刷新列表", self._reload),
                         ("下载模型", self._pull),
                         ("删除模型", self._delete)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self._reload()

    def _refresh_status(self):
        mode = self.settings.get("model_mode", "cloud")
        backend = self.settings.get("local_backend", "embedded")
        model = self.settings.get("local_model", "deepseek-r1:7b")
        if mode == "cloud":
            text = "当前生效：云端 API"
        elif backend == "embedded":
            text = "当前生效：本地 · 内嵌模型（DeepSeek R1 7B）"
        else:
            text = f"当前生效：本地 · Ollama / {model}"
        self.status_label.setText(text)

    def _use_cloud(self):
        self.settings.set("model_mode", "cloud")
        self._refresh_status()
        QMessageBox.information(self, "已生效", "AI 翻译将使用云端 API（设置 → API 接口管理中配置密钥）")

    def _use_embedded(self):
        self.settings.set("model_mode", "local")
        self.settings.set("local_backend", "embedded")
        self._refresh_status()
        QMessageBox.information(self, "已生效", "AI 翻译将使用软件内嵌的 DeepSeek R1 7B 模型")

    def _reload(self):
        self.list.clear()
        self.list.addItem("加载中…")
        self._worker = _ListWorker(self.settings)
        self._worker.done.connect(self._fill)
        self._worker.error.connect(self._list_error)
        self._worker.start()

    def _fill(self, models):
        self.list.clear()
        self.list.addItems(models or ["（本机暂无模型，可点击“下载模型”）"])

    def _list_error(self, msg):
        self.list.clear()
        self.list.addItem(f"无法连接 Ollama：{msg}")

    def _select(self, item):
        name = item.text()
        if name.startswith(("（", "无法", "加载")):
            return
        # 三个键一起设置，确保点击后 AI 翻译立即走该模型
        self.settings.set("model_mode", "local")
        self.settings.set("local_backend", "ollama")
        self.settings.set("local_model", name)
        self._refresh_status()
        QMessageBox.information(self, "已生效", f"AI 翻译将使用本地模型：{name}")

    def _pull(self):
        name, ok = QInputDialog.getText(self, "下载模型",
                                        "输入 Ollama 模型名（如 deepseek-r1:7b）：")
        if ok and name.strip():
            import subprocess, shutil
            ollama = shutil.which("ollama")
            if not ollama:
                QMessageBox.critical(self, "错误", "未找到 ollama 命令，请先安装并启动 Ollama")
                return
            subprocess.Popen(["ollama", "pull", name.strip()],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)

    def _delete(self):
        item = self.list.currentItem()
        if not item:
            return
        name = item.text()
        import subprocess, shutil
        ollama = shutil.which("ollama")
        if ollama and QMessageBox.question(self, "确认", f"删除本地模型 {name}？") \
                == QMessageBox.StandardButton.Yes:
            subprocess.run([ollama, "rm", name], capture_output=True)
            self._reload()
