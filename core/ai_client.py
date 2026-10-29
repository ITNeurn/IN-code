# -*- coding: utf-8 -*-
"""
AI 客户端模块
=============
两套模型方案：
  1. 云端 DeepSeek API（OpenAI 兼容接口 https://api.deepseek.com）
  2. 本地 Ollama 模型（默认 deepseek-r1:7b，需本机已启动 Ollama 服务）

AI 只作为"翻译器"：把用户梳理好的自然语言逻辑流程翻译成标准源代码。
解析协议：
  - 成功：直接输出代码本身（可带 ``` 代码块，客户端负责剥离）。
  - 无法理解：{INX}print：（无法理解的内容）{INY} → 理解故障弹窗。
  - 需要第三方库：{UNX}text：（库名称）{UNY} → 自动安装后重试翻译。
所有网络请求都放在 QThread 工作线程中执行，不阻塞界面。
"""
import re
import sys
import requests
from PyQt6.QtCore import QThread, pyqtSignal

from config.settings import VENV_DIR

# 理解故障标记（旧协议，保留兼容）
FAILURE_MARK = "[[理解故障]]"

# 新协议标记：{INX}…{INY} = 无法理解的内容；{UNX}…{UNY} = 需要安装的第三方库
FAIL_OPEN, FAIL_CLOSE = "{INX}", "{INY}"
LIB_OPEN, LIB_CLOSE = "{UNX}", "{UNY}"

FAIL_RE = re.compile(r"\{INX\}(.*?)\{INY\}", re.S)
LIB_RE = re.compile(r"\{UNX\}(.*?)\{UNY\}", re.S)

# 系统提示词：约束模型只做"逻辑 → 代码"的翻译，不做自由发挥
SYSTEM_PROMPT = """你是一个编程翻译器。用户会用自然语言给出完整的程序逻辑流程（步骤、条件、循环等），
你的唯一任务是把这些逻辑忠实地翻译成 {lang} 标准源代码，不要添加用户没有描述的功能。

规则：
1. 在输出代码时要直接输出，不能有任何多余内容：不要解释、不要寒暄；
   严禁使用任何代码块包裹标记，包括 ```、~~~、{{python}}、[python]、<python> 等，
   直接输出源代码本身。
2. 在遇到无法理解的内容片段时要输出函数：
{fail_open}print：（无法理解的内容）{fail_close}
3. 只有当你的代码确实 import 了 Python 标准库以外的第三方模块、且该模块不属于内置能力时，
才输出：
{lib_open}text：（pip 包名称）{lib_close}
   注意：print、input、len、range、sum、sorted 等内置函数，以及 json、os、sys、math、
   random、time、re、datetime、collections、itertools、tkinter、csv、sqlite3、pathlib
   等标准库都无需安装，严禁为它们输出该标记；一次只请求真正缺少的库，不确定时不要输出。
4. 自然语言中的动作/控制词必须翻译成对应的语法结构，不能当作字符串内容：
   「输出/打印/显示」→ print；「输入/读入」→ input；「循环/重复」→ for/while；
   「如果/若」→ if；「否则/不然」→ else；「返回」→ return；「定义函数/方法」→ def；
   「列表/数组」→ list/[]；「字典」→ dict/{{}}。只有除去这些动作词之后的名词或数值
   才是字面量内容。例如：「输出飞行」→ print("飞行")，而非 print("输出飞行")；
   「输出你好世界」→ print("你好世界")；「输入姓名」→ input("姓名")。
5. 代码必须可以直接编译/运行，包含必要的入口（如 main）。"""

# 各语言的附加约束（追加在系统提示词末尾）
LANG_RULES = {
    "java": "\n6. Java 代码必须只包含一个 public class Main，"
            "入口为 public static void main(String[] args)；不要输出 package 语句；"
            "不要使用第三方库（{unx}…{uny} 协议仅对 Python 有效）。",
    "h5": "\n6. H5 代码必须是一个完整独立的 HTML 文件：以 <!DOCTYPE html> 开头，"
          "CSS 写在 <style> 中、JavaScript 写在 <script> 中，全部内联，"
          "不引用任何外部文件，保存后可直接用浏览器打开运行。",
    "python": "",
    "c": "",
    "cpp": "",
}


def system_prompt(lang: str) -> str:
    """生成系统提示词（把协议标记与语言专属约束填入模板）。"""
    return SYSTEM_PROMPT.format(lang=lang, fail_open=FAIL_OPEN, fail_close=FAIL_CLOSE,
                                lib_open=LIB_OPEN, lib_close=LIB_CLOSE) + \
        LANG_RULES.get(lang, "").format(unx=LIB_OPEN, uny=LIB_CLOSE)


class AIResult:
    """一次 AI 调用的结果。"""
    def __init__(self, ok: bool, code: str = "", fail_reason: str = "", error: str = "",
                 packages: list[str] | None = None, retry_hint: str = ""):
        self.ok = ok                    # 是否成功拿到代码
        self.code = code                # 生成的源代码
        self.fail_reason = fail_reason  # 理解故障原因（AI 主动返回）
        self.error = error              # 网络/接口错误（软件层面）
        self.packages = packages or []  # AI 要求安装的第三方库（{UNX}…{UNY}）
        self.retry_hint = retry_hint    # 非空表示需带着该提示自动重新翻译


# 代码块围栏匹配（支持 ```lang、~~~lang、{lang}、[lang]、<lang> 等多种模型输出风格）
_OPEN_FENCE = re.compile(r"^(`{3,}|~{3,})\s*[\w.+-]*\s*$")
_CLOSE_FENCE = re.compile(r"^(`{3,}|~{3,})\s*[\w.+-]*\s*$")
_TAG_OPEN = re.compile(r"^\{[\w.]+\}$|^\[[\w.]+\]$|^<[\w.]+>$")
_TAG_CLOSE = re.compile(r"^\{/[\w.]+\}$|^\[/[\w.]+\]$|^</[\w.]+>$")
_TRAILING_TAG = re.compile(r"\s*(\{/[\w.]+\}|\[/[\w.]+\]|</[\w.]+>)\s*$")


def strip_code_fence(text: str) -> str:
    """剥离模型可能输出的各种代码块包裹，避免围栏标记混入源码。

    支持 ``` ```、~~~ ~~~、{lang}…{/lang}、[lang]…[/lang]、<lang>…</lang>
    等格式；对首尾残留的单独围栏行也会清理。
    """
    text = text.strip()
    # 优先从三反引号围栏中提取正文（含围栏前后有说明文字的情形）
    m = re.search(r"```(?:\w+)?\s*\n(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    # 行级清理：去掉首尾的围栏/标签行
    lines = text.splitlines()
    while lines and (_OPEN_FENCE.match(lines[0].strip())
                     or _TAG_OPEN.match(lines[0].strip())):
        lines.pop(0)
    while lines and (_CLOSE_FENCE.match(lines[-1].strip())
                     or _TAG_CLOSE.match(lines[-1].strip())):
        lines.pop()
    text = "\n".join(lines).strip()
    # 兜底：去掉行末残留的关闭标签 {/xxx} [/xxx] </xxx>
    text = _TRAILING_TAG.sub("", text).strip()
    return text


def _clean_inner(s: str) -> str:
    """清洗协议标记内的文本：去掉 print：/text： 前缀与外层括号。"""
    s = s.strip()
    s = re.sub(r"^\s*(print|text)\s*[：:]\s*", "", s, flags=re.I).strip()
    if len(s) >= 2 and s[0] in "（(" and s[-1] in "）)":
        s = s[1:-1].strip()
    return s


def _extract_packages(text: str) -> list[str]:
    """从 {UNX}…{UNY} 中提取库名（支持逗号/顿号/空格分隔的多个库）。"""
    out: list[str] = []
    for m in LIB_RE.finditer(text):
        for part in re.split(r"[，,、;；\s]+", _clean_inner(m.group(1))):
            p = part.strip()
            if p and re.fullmatch(r"[A-Za-z0-9_.\-]{1,64}", p) and p not in out:
                out.append(p)
    return out


# 常见「导入名 → pip 包名」映射：模型常写成 import 名，直接 pip 会装不上
MODULE_TO_PIP = {
    "cv2": "opencv-python", "pil": "Pillow", "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4", "yaml": "PyYAML", "serial": "pyserial",
    "crypto": "pycryptodome", "dateutil": "python-dateutil", "fitz": "PyMuPDF",
    "docx": "python-docx", "pptx": "python-pptx", "win32api": "pywin32",
    "psycopg2": "psycopg2-binary", "telebot": "pyTelegramBotAPI",
    "telegram": "python-telegram-bot", "opengl": "PyOpenGL", "usb": "pyusb",
    "jwt": "PyJWT", "dotenv": "python-dotenv", "grpc": "grpcio",
    "mpl_toolkits": "matplotlib", "google": "google-api-python-client",
}
_PIP_TO_MODULE = {v.replace("-", "_").lower(): k for k, v in MODULE_TO_PIP.items()}

_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([^\n#]+))", re.M)


def _code_imports(code: str) -> set[str]:
    """提取代码中 import 的顶层模块名（小写）。"""
    mods: set[str] = set()
    for m in _IMPORT_RE.finditer(code):
        if m.group(1):
            mods.add(m.group(1).split(".")[0].lower())
        else:
            for part in m.group(2).split(","):
                name = part.strip().split(" as ")[0].strip().split(".")[0]
                if re.fullmatch(r"[A-Za-z_]\w*", name):
                    mods.add(name.lower())
    return mods


def _venv_has_module(name: str) -> bool:
    """检查隔离 venv 的 site-packages 中是否已有该模块（避免误判为缺失）。"""
    sp = VENV_DIR / "Lib" / "site-packages"
    if not sp.is_dir():
        return False
    key = name.replace("-", "_").lower()
    try:
        for p in sp.iterdir():
            n = p.name.lower()
            if n == key or n.startswith(key + "-") or n.startswith(key + "."):
                return True
    except OSError:
        return False
    return False


def _filter_packages(packages: list[str], code: str) -> list[str]:
    """过滤 AI 的装库请求：剔除幻觉、标准库、已安装、代码未真正 import 的模块。

    只有「代码中确实 import 了、且当前隔离环境里确实没有」的模块才需要安装；
    没有代码可交叉验证时一律不安装。
    """
    if not code:
        return []
    imports = _code_imports(code)
    out: list[str] = []
    for pkg in packages:
        key = pkg.replace("-", "_").split(".")[0].lower()
        if key in MODULE_TO_PIP:            # 模型写的是导入名（cv2 → opencv-python）
            module, pip_name = key, MODULE_TO_PIP[key]
        elif key in _PIP_TO_MODULE:         # 模型写的是 pip 名（opencv-python → cv2）
            module, pip_name = _PIP_TO_MODULE[key], pkg
        else:
            module, pip_name = key, pkg
        if module in sys.stdlib_module_names or _venv_has_module(module):
            continue                       # 标准库 / 已装好，无需安装
        if module not in imports:
            continue                       # 代码根本没用到这个库（模型幻觉/无效请求）
        if pip_name not in out:
            out.append(pip_name)
    return out


def parse_ai_reply(text: str, lang: str) -> AIResult:
    """把模型原始回复解析成 AIResult（理解故障 / 库请求 / 正常代码）。"""
    text = text.strip()
    # DeepSeek-R1 系列会先输出 <think>…</think> 推理过程，剥离掉
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # 1) 无法理解的内容：{INX}print：（原因）{INY}
    m = FAIL_RE.search(text)
    if m:
        return AIResult(ok=False, fail_reason=_clean_inner(m.group(1)) or "描述不完整")
    # 旧协议兼容：[[理解故障]]原因
    if text.startswith(FAILURE_MARK):
        return AIResult(ok=False,
                        fail_reason=text[len(FAILURE_MARK):].strip() or "描述不完整")

    # 2) 取出代码（先删掉库标记，避免标记混进源码）
    raw_packages = _extract_packages(text)
    code = strip_code_fence(LIB_RE.sub("", text))

    # 3) 需要安装第三方库：只保留代码真正 import 且环境里确实缺少的库
    packages = _filter_packages(raw_packages, code) if raw_packages else []
    if packages:
        return AIResult(ok=False, code=code, packages=packages)
    if raw_packages:
        if code:
            # 请求无效（幻觉/标准库/已安装/代码没用到）：直接用代码
            return AIResult(ok=True, code=code)
        # 只有库标记、没有代码：无法判断是否真需要，交给 pip 装可能装到幻觉库
        bad = "、".join(raw_packages)
        return AIResult(ok=False, retry_hint=(
            f"你上一次只输出了库安装标记（{bad}），没有输出代码。"
            "请直接输出完整可运行的代码；只有当代码确实 import 了第三方模块时，"
            "才在代码之后附带库安装标记。标准库和内置函数绝不需要安装。"))

    # 4) 正常代码
    if not code:
        return AIResult(ok=False, fail_reason="模型未返回任何代码")
    return AIResult(ok=True, code=code)


class AIWorker(QThread):
    """后台 AI 请求线程。

    信号：
      finished_ok(AIResult)  请求完成（无论成功或理解故障，看 result.ok）
    """
    finished_ok = pyqtSignal(object)

    def __init__(self, settings, description: str, language: str, parent=None,
                 extra_hint: str = ""):
        super().__init__(parent)
        self.settings = settings
        self.description = description
        self.language = language
        self.extra_hint = extra_hint

    @property
    def user_content(self) -> str:
        """用户消息：描述 + 可选的补充提示（如"这些库已安装"）。"""
        if self.extra_hint:
            return f"{self.description}\n\n{self.extra_hint}"
        return self.description

    # ------------------------------------------------------------ 主流程
    def run(self):
        try:
            if self.settings.get("model_mode") == "local":
                raw = self._call_ollama()
            else:
                raw = self._call_deepseek()
            self.finished_ok.emit(parse_ai_reply(raw, self.language))
        except Exception as e:  # 网络错误、服务未启动等统一走 error
            self.finished_ok.emit(AIResult(ok=False, error=str(e)))

    # ------------------------------------------------------------ 云端 DeepSeek
    def _call_deepseek(self) -> str:
        api_key = self.settings.get("api_key", "").strip()
        if not api_key:
            raise RuntimeError("尚未配置云端 API 密钥，请到 设置 → API接口管理 中填写")
        base = self.settings.get("api_base", "https://api.deepseek.com").rstrip("/")
        resp = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self.settings.get("cloud_model", "deepseek-chat"),
                "messages": [
                    {"role": "system",
                     "content": system_prompt(self.language)},
                    {"role": "user", "content": self.user_content},
                ],
                "temperature": 0.2,
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    # ------------------------------------------------------------ 本地模式
    def _call_ollama(self) -> str:
        """本地模式：优先使用软件内嵌推理引擎（llama-server + 内置 GGUF），
        内嵌引擎不可用时回退到本机 Ollama 服务。"""
        backend = self.settings.get("local_backend", "embedded")
        if backend == "embedded":
            try:
                return self._call_embedded()
            except Exception:
                # 内嵌引擎失败时尝试 Ollama 兜底
                return self._call_ollama_http()
        return self._call_ollama_http()

    def _call_embedded(self) -> str:
        """通过内嵌 llama-server（OpenAI 兼容接口）推理。"""
        from .local_engine import LocalEngine
        engine = LocalEngine(self.settings)
        base = engine.start()
        resp = requests.post(
            f"{base}/chat/completions",
            json={
                "model": "embedded",
                "messages": [
                    {"role": "system",
                     "content": system_prompt(self.language)},
                    {"role": "user", "content": self.user_content},
                ],
                "temperature": 0.2,
                "stream": False,
            },
            timeout=1800,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_ollama_http(self) -> str:
        """调用本机 Ollama 服务（需用户已安装并启动 Ollama）。"""
        host = self.settings.get("ollama_host", "http://localhost:11434").rstrip("/")
        model = self.settings.get("local_model", "deepseek-r1:7b")
        try:
            resp = requests.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system",
                         "content": system_prompt(self.language)},
                        {"role": "user", "content": self.user_content},
                    ],
                    "stream": False,
                },
                timeout=600,
            )
            resp.raise_for_status()
        except requests.ConnectionError:
            raise RuntimeError("内嵌引擎不可用，且无法连接本地 Ollama 服务，请先在本机启动 Ollama")
        return resp.json()["message"]["content"]


class ChatWorker(QThread):
    """自由问答线程（传统模式"向AI提问"），不做代码翻译约束。"""
    done = pyqtSignal(str)     # 回复文本
    error = pyqtSignal(str)

    def __init__(self, settings, question: str, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.question = question

    def run(self):
        try:
            if self.settings.get("model_mode") == "local":
                # 本地模式：内嵌引擎优先，Ollama 兜底
                if self.settings.get("local_backend", "embedded") == "embedded":
                    try:
                        from .local_engine import LocalEngine
                        base = LocalEngine(self.settings).start()
                        resp = requests.post(
                            f"{base}/chat/completions",
                            json={"model": "embedded",
                                  "messages": [{"role": "user", "content": self.question}],
                                  "stream": False}, timeout=1800)
                        resp.raise_for_status()
                        self.done.emit(resp.json()["choices"][0]["message"]["content"])
                        return
                    except Exception:
                        pass  # 回退 Ollama
                host = self.settings.get("ollama_host", "http://localhost:11434").rstrip("/")
                resp = requests.post(
                    f"{host}/api/chat",
                    json={"model": self.settings.get("local_model", "deepseek-r1:7b"),
                          "messages": [{"role": "user", "content": self.question}],
                          "stream": False}, timeout=600)
                resp.raise_for_status()
                self.done.emit(resp.json()["message"]["content"])
            else:
                api_key = self.settings.get("api_key", "").strip()
                if not api_key:
                    raise RuntimeError("尚未配置云端 API 密钥")
                base = self.settings.get("api_base", "https://api.deepseek.com").rstrip("/")
                resp = requests.post(
                    f"{base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": self.settings.get("cloud_model", "deepseek-chat"),
                          "messages": [{"role": "user", "content": self.question}],
                          "stream": False}, timeout=120)
                resp.raise_for_status()
                self.done.emit(resp.json()["choices"][0]["message"]["content"])
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------- 辅助接口
def fetch_balance(settings) -> str:
    """查询 DeepSeek API 余额（OpenAI 兼容的 /user/balance 接口）。"""
    api_key = settings.get("api_key", "").strip()
    if not api_key:
        return "未配置 API 密钥"
    base = settings.get("api_base", "https://api.deepseek.com").rstrip("/")
    try:
        resp = requests.get(f"{base}/user/balance",
                            headers={"Authorization": f"Bearer {api_key}"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        infos = data.get("balance_infos", [])
        if infos:
            return f"{infos[0].get('total_balance', '?')} {infos[0].get('currency', '')}"
        return "查询成功，但无余额信息"
    except Exception as e:
        return f"查询失败：{e}"


def list_ollama_models(settings) -> list[str]:
    """列出本机 Ollama 已安装的模型。"""
    host = settings.get("ollama_host", "http://localhost:11434").rstrip("/")
    resp = requests.get(f"{host}/api/tags", timeout=10)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]
