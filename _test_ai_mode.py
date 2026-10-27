# -*- coding: utf-8 -*-
"""AI 模式专项测试：解析协议 + AIWorker 线程（mock 网络）+ 主窗口翻译流程。

全程不访问真实网络、不写真实配置（直接改 _data 绕过 save）：
  - parse_ai_reply / strip_code_fence：代码块剥离、think 剥离、理解故障协议
  - AIWorker：云端成功/故障/无密钥、本地内嵌失败回退 Ollama、Ollama 断连
  - MainWindow：空描述拦截、翻译成功写入三处代码、故障弹窗、错误弹窗
"""
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication, QMessageBox

app = QApplication([])

import core.ai_client as ai
from config.settings import Settings
from ui import main_window as mw_mod
from ui.main_window import MainWindow

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def make_settings(**overrides):
    """构造不写磁盘的 Settings（测试直接改内存，避免污染用户配置）。"""
    s = Settings()
    s._data.update(overrides)
    return s


class _FakeResp:
    """模拟 requests.post 的返回值。"""

    def __init__(self, content="", status=200):
        self._content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ai.requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return {"choices": [{"message": {"content": self._content}}],
                "message": {"content": self._content}}


def run_worker_sync(worker):
    """同步执行 worker.run() 并捕获 finished_ok 信号结果。"""
    results = []
    worker.finished_ok.connect(lambda r: results.append(r))
    worker.run()
    return results


# ================================================================ 一、解析层
check("纯代码原样返回",
      ai.parse_ai_reply("print(1)", "python").code == "print(1)")

r = ai.parse_ai_reply("```python\nprint(2)\n```", "python")
check("剥离 python 代码块", r.ok and r.code == "print(2)")

r = ai.parse_ai_reply("```c\nint main(){return 0;}\n```", "c")
check("剥离 c 代码块", r.ok and "main" in r.code)

r = ai.parse_ai_reply("<think>用户在要循环…</think>\nfor i in range(3):\n    print(i)",
                      "python")
check("剥离 think 推理段", r.ok and "<think>" not in r.code and "range" in r.code)

r = ai.parse_ai_reply("[[理解故障]]缺少循环终止条件", "python")
check("理解故障标记解析", (not r.ok) and r.fail_reason == "缺少循环终止条件")

r = ai.parse_ai_reply("[[理解故障]]", "python")
check("裸故障标记兜底文案", (not r.ok) and r.fail_reason == "描述不完整")

r = ai.parse_ai_reply("   ", "python")
check("空回复视为故障", (not r.ok) and r.fail_reason == "模型未返回任何代码")

# ---------------- 新协议 {INX}/{INY} 与 {UNX}/{UNY}
r = ai.parse_ai_reply("{INX}print：（没有说明循环终止条件）{INY}", "python")
check("新协议理解故障", (not r.ok) and r.fail_reason == "没有说明循环终止条件")

r = ai.parse_ai_reply("{INX}print：循环次数不明{INY}", "python")
check("新协议无括号故障", (not r.ok) and r.fail_reason == "循环次数不明")

r = ai.parse_ai_reply("{UNX}text：（numpy）{UNY}", "python")
check("新协议库请求", (not r.ok) and r.packages == ["numpy"])

r = ai.parse_ai_reply("{UNX}text：（numpy、pandas，requests）{UNY}", "python")
check("新协议多库解析", r.packages == ["numpy", "pandas", "requests"])

r = ai.parse_ai_reply("{UNX}text：opencv-python{UNY}", "python")
check("新协议无括号库名", r.packages == ["opencv-python"])

r = ai.parse_ai_reply("{INX}print：（无法理解）{INY}{UNX}text：（numpy）{UNY}", "python")
check("故障优先于库请求", (not r.ok) and r.fail_reason == "无法理解" and not r.packages)

# 系统提示词必须能正常渲染（新标记含花括号，不能被 format 吃掉）
p = ai.system_prompt("python")
check("系统提示词渲染", "{INX}print" in p and "{UNX}text" in p and "python" in p)

# ================================================================ 二、AIWorker（mock 网络）
orig_post = ai.requests.post

# 云端成功
ai.requests.post = lambda *a, **kw: _FakeResp("```python\nprint('ok')\n```")
s = make_settings(model_mode="cloud", api_key="sk-test", api_base="https://api.deepseek.com")
res = run_worker_sync(ai.AIWorker(s, "1. 输出ok", "python"))[0]
check("云端翻译成功并剥离代码块", res.ok and res.code == "print('ok')")

# 云端返回理解故障
ai.requests.post = lambda *a, **kw: _FakeResp("[[理解故障]]描述里没有说明循环几次")
res = run_worker_sync(ai.AIWorker(s, "循环打印", "python"))[0]
check("云端理解故障透传", (not res.ok) and "循环几次" in res.fail_reason)

# 云端无 API 密钥 → error 而非崩溃
res = run_worker_sync(ai.AIWorker(make_settings(model_mode="cloud", api_key=""),
                                  "x", "python"))[0]
check("无密钥走 error 分支", (not res.ok) and "尚未配置" in res.error)

# 本地：内嵌引擎抛异常 → 回退 Ollama HTTP 成功
def _local_post(url, **kw):
    if "11434" in url:
        return _FakeResp("print('from ollama')")
    raise ConnectionError("embedded down")

ai.requests.post = _local_post
import core.local_engine as le
orig_start = le.LocalEngine.start
le.LocalEngine.start = lambda self: (_ for _ in ()).throw(RuntimeError("no embedded"))
s = make_settings(model_mode="local", local_backend="embedded",
                  ollama_host="http://localhost:11434", local_model="deepseek-r1:7b")
res = run_worker_sync(ai.AIWorker(s, "1. 输出", "python"))[0]
check("本地内嵌失败回退Ollama", res.ok and "ollama" in res.code)

# 本地：内嵌失败 + Ollama 断连 → error
ai.requests.post = lambda *a, **kw: (_ for _ in ()).throw(
    ai.requests.ConnectionError("refused"))
res = run_worker_sync(ai.AIWorker(s, "1. 输出", "python"))[0]
check("Ollama断连给出可读错误", (not res.ok) and "Ollama" in res.error)

le.LocalEngine.start = orig_start
ai.requests.post = orig_post

# ================================================================ 三、主窗口 AI 模式流程
# mock 弹窗，避免阻塞 / 依赖真实界面
info_calls, crit_calls, fail_dlg = [], [], []
mw_mod.QMessageBox.information = lambda *a, **kw: info_calls.append(a)
mw_mod.QMessageBox.critical = lambda *a, **kw: crit_calls.append(a)


class _FakeFailDlg:
    def __init__(self, reason, parent=None):
        fail_dlg.append(reason)

    def exec(self):
        return 0


mw_mod.UnderstandFailureDialog = _FakeFailDlg

win = MainWindow()
check("默认AI模式", win.stack.currentWidget() is win.ai_page)

# 空描述：拦截并提示，不启动 worker
win.ai_page.set_description("")
win._run()
check("空描述被拦截提示", bool(info_calls) and win._ai_worker is None)

# 翻译成功：代码写入 ai_page / trad_page / project，并进入运行
ai.requests.post = lambda *a, **kw: _FakeResp("print('hello ai')")
win.settings._data.update(model_mode="cloud", api_key="sk-test")
ran = []
win._start_run = lambda code: ran.append(code)   # 不真正运行，只记录
win.ai_page.set_description("1. 输出 hello ai")
win._run()
win._ai_worker.wait(5000)
app.processEvents()
check("翻译成功写入AI内部代码", win.ai_page.code() == "print('hello ai')")
check("翻译成功同步传统编辑器", win.trad_page.code() == "print('hello ai')")
check("翻译成功写入项目", win.project.generated_code == "print('hello ai')")
check("翻译成功后触发运行", ran == ["print('hello ai')"])
check("编译弹窗已关闭", not win._compile_dlg.isVisible())

# 理解故障：弹故障页，不运行
ai.requests.post = lambda *a, **kw: _FakeResp("[[理解故障]]没有说明输入来源")
win.ai_page.set_description("读一下再处理")
ran.clear()
win._run()
win._ai_worker.wait(5000)
app.processEvents()
check("理解故障弹窗展示原因", fail_dlg == ["没有说明输入来源"])
check("理解故障不触发运行", ran == [])

# 网络异常：error 弹窗
ai.requests.post = lambda *a, **kw: (_ for _ in ()).throw(
    ai.requests.ConnectionError("timeout"))
win.ai_page.set_description("1. 输出1")
win._run()
win._ai_worker.wait(5000)
app.processEvents()
check("网络异常弹错误框", any("timeout" in str(c) for c in crit_calls))

# ---------------- AI 请求安装第三方库 → 自动安装并重试翻译
from PyQt6.QtCore import QObject, pyqtSignal as _sig

started_pkgs, retried, fake_workers = [], [], []


class _FakeLibWorker(QObject):
    progress = _sig(str)
    finished_all = _sig(bool)

    def __init__(self, packages, parent=None):
        super().__init__(parent)
        self.packages = packages
        fake_workers.append(self)

    def start(self):
        started_pkgs.append(list(self.packages))


mw_mod.LibraryInstallWorker = _FakeLibWorker
mw_mod.QMessageBox.warning = lambda *a, **kw: None

ai.requests.post = lambda *a, **kw: _FakeResp("{UNX}text：（numpy）{UNY}")
win.ai_page.set_description("用 numpy 计算平均分")
ran.clear()
win._run()
win._ai_worker.wait(5000)
app.processEvents()
check("库请求触发自动安装", started_pkgs == [["numpy"]])
check("库请求不直接运行", ran == [])

win._run = lambda: retried.append(True)
fake_workers[-1].finished_all.emit(True)
check("装库成功自动重试翻译", retried == [True])

# 连续多轮要求装库时停止自动重试（防死循环）
win._lib_retry = 3
win._auto_install_and_retry(["x"])
check("超过3轮停止自动重试", win._lib_retry == 0)

# ================================================================ 四、APK 导出模块
from core import android_exporter as ax

check("WSL 路径转换", ax.to_wsl_path(r"C:\Users\PC\Desktop") == "/mnt/c/Users/PC/Desktop")
check("buildozer.spec 渲染",
      "kivy" in ax.BUILDOZER_SPEC.format(title="t", package="p",
                                         requirements="python3,kivy"))
check("WSL 检测不崩溃", isinstance(ax.wsl_distros(), list))

req = ax.requirements_for(
    "import numpy\nimport cv2\nfrom PIL import Image\n"
    "from kivy.app import App\nimport os\nimport json")
check("APK依赖推导含第三方库",
      all(x in req for x in ("numpy", "opencv", "pillow")))
check("APK依赖推导含kivy", "kivy" in req)
check("APK依赖排除标准库", "os" not in req.split(",") and "json" not in req.split(","))

# ================================================================ 五、本地模型选择页（生效路径）
from ui.pages import local_model_page as lmp

lmp.QMessageBox.information = lambda *a, **kw: None


class _FakeSettings:
    """只读内存、不落盘的 settings（测试页逻辑用）。"""

    def __init__(self):
        self.d = {"model_mode": "cloud", "local_backend": "embedded",
                  "local_model": "deepseek-r1:7b", "ollama_host": "http://localhost:11434",
                  "model_storage": r"C:\temp\nonexistent"}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


fs = _FakeSettings()
page = lmp.LocalModelPage(fs)
check("初始状态显示云端", "云端 API" in page.status_label.text())

page._use_embedded()
check("切内嵌模型", fs.d["model_mode"] == "local" and fs.d["local_backend"] == "embedded")
check("内嵌状态文案", "内嵌模型" in page.status_label.text())


class _Item:
    def __init__(self, t):
        self._t = t

    def text(self):
        return self._t


page._select(_Item("deepseek-r1:14b"))
check("选Ollama模型三键联动",
      fs.d["model_mode"] == "local" and fs.d["local_backend"] == "ollama"
      and fs.d["local_model"] == "deepseek-r1:14b")
check("Ollama状态文案", "Ollama / deepseek-r1:14b" in page.status_label.text())

# 占位文本不可选中
before = dict(fs.d)
page._select(_Item("（本机暂无模型，可点击“下载模型”）"))
check("占位项点击无效", fs.d == before)

page._use_cloud()
check("切回云端", fs.d["model_mode"] == "cloud" and "云端 API" in page.status_label.text())

ai.requests.post = orig_post

print()
print("失败用例:", failures if failures else "无")
sys.exit(1 if failures else 0)
