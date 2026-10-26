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
import requests
from PyQt6.QtCore import QThread, pyqtSignal

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
1. 在输出代码时要直接输出，不能有任何多余内容：不要解释、不要寒暄、不要使用 Markdown 代码块标记。
2. 在遇到无法理解的内容片段时要输出函数：
{fail_open}print：（无法理解的内容）{fail_close}
3. 在遇到需要安装第三方库的时候输出函数：
{lib_open}text：（库名称）{lib_close}
4. 代码必须可以直接编译/运行，包含必要的入口（如 main）。"""


def system_prompt(lang: str) -> str:
    """生成系统提示词（把协议标记填入模板）。"""
    return SYSTEM_PROMPT.format(lang=lang, fail_open=FAIL_OPEN, fail_close=FAIL_CLOSE,
                                lib_open=LIB_OPEN, lib_close=LIB_CLOSE)


class AIResult:
    """一次 AI 调用的结果。"""

    def __init__(self, ok: bool, code: str = "", fail_reason: str = "", error: str = "",
                 packages: list[str] | None = None):
        self.ok = ok                    # 是否成功拿到代码
        self.code = code                # 生成的源代码
        self.fail_reason = fail_reason  # 理解故障原因（AI 主动返回）
        self.error = error              # 网络/接口错误（软件层面）
        self.packages = packages or []  # AI 要求安装的第三方库（{UNX}…{UNY}）


def strip_code_fence(text: str) -> str:
    """剥离模型可能输出的 ``` 代码块包裹。"""
    text = text.strip()
    m = re.search(r"```(?:\w+)?\s*\n(.*?)```", text, re.S)
    return m.group(1).strip() if m else text


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

    # 2) 需要安装第三方库：{UNX}text：（库名）{UNY}
    packages = _extract_packages(text)
    if packages:
        return AIResult(ok=False, packages=packages)

    # 3) 正常代码
    code = strip_code_fence(text)
    if not code:
        return AIResult(ok=False, fail_reason="模型未返回任何代码")
    return AIResult(ok=True, code=code)


class AIWorker(QThread):
    """后台 AI 请求线程。

    信号：
      finished_ok(AIResult)  请求完成（无论成功或理解故障，看 result.ok）
    """
    finished_ok = pyqtSignal(object)

    def __init__(self, settings, description: str, language: str, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.description = description
        self.language = language

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
                    {"role": "user", "content": self.description},
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
                    {"role": "user", "content": self.description},
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
                        {"role": "user", "content": self.description},
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
