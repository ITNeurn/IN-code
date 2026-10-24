# -*- coding: utf-8 -*-
"""运行环境测试：venv 隔离运行 + 行追踪。"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from core.compiler import RunWorker

app = QApplication([])
lines, outs = [], []
code = "a = 0\nfor i in range(5):\n    a += i\nprint('sum =', a)\n"
w = RunWorker(code, "python")
w.output.connect(lambda s: outs.append(s))
w.line_changed.connect(lambda n: lines.append(n))
w.failed.connect(lambda m: (print("FAILED:", m), app.exit(1)))
w.done.connect(lambda c: (print("exit code", c), app.exit(0)))
w.start()
QTimer.singleShot(180000, lambda: app.exit(2))
rc = app.exec()
text = "".join(outs)
print("OUT:", text.strip())
print("LINES seen:", sorted(set(x for x in lines if x > 0)))
ok = "sum = 10" in text and any(x > 0 for x in lines) and rc == 0
print("TEST PASS" if ok else "TEST FAIL")
sys.exit(0 if ok else 1)
