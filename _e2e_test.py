# -*- coding: utf-8 -*-
"""端到端测试：内嵌引擎 + R1 7B 翻译自然语言流程为代码。"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from config.settings import Settings
from core.ai_client import AIWorker

app = QApplication([])
s = Settings()
s.set("model_mode", "local")
s.set("local_backend", "embedded")

desc = "1. 让用户输入名字 2. 输出 Hello, 名字!"
w = AIWorker(s, desc, "python")
result = {}
w.finished_ok.connect(lambda r: (result.update(r=r), app.quit()))
w.start()
QTimer.singleShot(600000, app.quit)
app.exec()

r = result.get("r")
print("ok:", r.ok, "| error:", r.error, "| fail:", r.fail_reason)
print("CODE:", r.code[:400])
print("E2E PASS" if r.ok and "input" in r.code else "E2E FAIL")
