# -*- coding: utf-8 -*-
"""
AI 客户端模块
=============
两套模型方案：
  1. 云端 DeepSeek API（OpenAI 兼容接口 https://api.deepseek.com）
  2. 本地 Ollama 模型（默认 deepseek-r1:7b，需本机已启动 Ollama 服务）

AI 只作为"翻译器"：把用户梳理好的自然语言逻辑流程翻译成标准源代码。
解析协议：
  - 成功：仅输出代码本身（可带 ``` 代码块，客户端负责剥离）。
  - 失败：以 [[理解故障]] 开头，后接无法理解的原因，供"理解故障"弹窗展示。
所有网络请求都放在 QThread 工作线程中执行，不阻塞界面。
"""
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal

# 理解故障标记：模型无法解析用户逻辑时以此开头回复
FAILURE_MARK = "[[理解故障]]"

# 系统提示词：约束模型只做"逻辑 → 代码"的翻译，不做自由发挥
SYSTEM_PROMPT = """你是一个编程翻译器。用户会用自然语言给出完整的程序逻辑流程（步骤、条件、循环等），
你的唯一任务是把这些逻辑忠实地翻译成 {lang} 标准源代码，不要添加用户没有描述的功能。

规则：
1. 只输出代码本身，不要解释，不要使用 Markdown 代码块标记。
2. 如果用户的描述逻辑不完整、存在矛盾或无法理解，不要编造代码，
   请只输出一行：{mark}无法理解的具体原因
3. 代码必须可以直接编译/运行，包含必要的入口（如 main）。"""


class AIResult:
    """一次 AI 调用的结果。"""

    def __init__(self, ok: bool, code: str = "", fail_reason: str = "", error: str = ""):
        self.ok = ok                    # 是否成功拿到代码
        self.code = code                # 生成的源代码
        self.fail_reason = fail_reason  # 理解故障原因（AI 主动返回）
        self.error = error              # 网络/接口错误（软件层面）


def strip_code_fence(text: str) -> str:
    """剥离模型可能输出的 ``` 代码块包裹。"""
    text = text.strip()
    m = re.search(r"```(?:\w+)?\s*\n(.*?)```", text, re.S)
    return m.group(1).strip() if m else text


def parse_ai_reply(text: str, lang: str) -> AIResult:
    """把模型原始回复解析成 AIResult（区分正常代码与理解故障）。"""
    text = text.strip()
    # DeepSeek-R1 系列会先输出 <think>…</think> 推理过程，剥离掉
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
    if text.startswith(FAILURE_MARK):
        return AIResult(ok=False, fail_reason=text[len(FAILURE_MARK):].strip() or "描述不完整")
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
                     "content": SYSTEM_PROMPT.format(lang=self.language, mark=FAILURE_MARK)},
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
                     "content": SYSTEM_PROMPT.format(lang=self.language, mark=FAILURE_MARK)},
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
                         "content": SYSTEM_PROMPT.format(lang=self.language, mark=FAILURE_MARK)},
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
