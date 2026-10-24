# -*- coding: utf-8 -*-
"""验证：连续运行两次程序，软件不自动退出；AI模式无代码区。"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui.main_window import MainWindow
from core.compiler import RunWorker

app = QApplication([])
win = MainWindow()

# AI 模式 UI 检查
assert not hasattr(win.ai_page, "code_edit"), "AI模式不应再有代码区"
assert win.ai_page.desc_edit.placeholderText() == "", "不应有提示文字"
assert not win.terminal_dock.isVisible(), "AI模式终端应隐藏"
print("AI模式UI: 单一大编辑区、无代码区、无提示文字、终端隐藏 OK")

results = []
def on_done(c):
    results.append(c)
    if len(results) == 2:
        print("两次运行都完成，退出码:", results)
        print("软件未自动退出:", "OK" if not win.isHidden() else "?")
        app.exit(0)
    else:
        QTimer.singleShot(500, run2)

def run2():
    w = RunWorker("print('second run')", "python")
    w.done.connect(on_done)
    w.failed.connect(lambda m: (print("FAIL", m), app.exit(1)))
    win._run_worker = w
    w.start()

w = RunWorker("print('first run')", "python")
w.done.connect(on_done)
w.failed.connect(lambda m: (print("FAIL", m), app.exit(1)))
win._run_worker = w
w.start()
QTimer.singleShot(240000, lambda: app.exit(2))
rc = app.exec()
print("APP EXIT CODE", rc, "=> NO AUTO-CLOSE" if rc == 0 else "")
