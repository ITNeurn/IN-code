# -*- coding: utf-8 -*-
"""
内嵌本地推理引擎
================
把 llama.cpp 官方 llama-server.exe 与 DeepSeek-R1-7B GGUF 模型一起打包进软件，
本地模式无需用户安装 Ollama 即可离线运行。

工作原理：
  1. 启动 llama-server 子进程（自带 OpenAI 兼容接口，监听 127.0.0.1:12987）
  2. 等待 /health 就绪
  3. AI 客户端通过 /v1/chat/completions 调用
"""
import subprocess
import time
from pathlib import Path

import requests

DEFAULT_PORT = 12987

# 引擎与模型的搜索路径（优先级从高到低）
# 1. 软件安装目录（打包后）2. 开发期 E 盘目录 3. 用户数据目录
def _candidate_dirs():
    import sys
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return [
        base / "runtime" / "llama",                       # 打包后的内置引擎
        Path(r"E:\Doubao\IN-code\runtime\llama"),         # 开发环境
        Path(r"E:\Doubao\CreativeCoder\runtime\llama"),   # 开发环境（旧目录）
        Path.home() / ".incode" / "runtime" / "llama",
    ]


def _candidate_models(settings=None):
    import sys
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    dirs = [
        base / "models",                                  # 打包后的内置模型
        Path(r"E:\Doubao\IN-code\models"),                # 开发环境
        Path(r"E:\Doubao\CreativeCoder\models"),          # 开发环境（旧目录）
        Path.home() / ".incode" / "models",
    ]
    if settings is not None:
        dirs.insert(0, Path(settings.get("model_storage")))
    return dirs


def find_server() -> Path | None:
    """定位 llama-server.exe。"""
    for d in _candidate_dirs():
        exe = d / "llama-server.exe"
        if exe.exists():
            return exe
    return None


def find_model(settings=None) -> Path | None:
    """定位内置 GGUF 模型文件。"""
    for d in _candidate_models(settings):
        if d.exists():
            ggufs = list(d.glob("*.gguf"))
            if ggufs:
                return ggufs[0]
    return None


class LocalEngine:
    """内嵌 llama-server 生命周期管理（全局单例使用）。"""

    def __init__(self, settings=None, port: int = DEFAULT_PORT):
        self.settings = settings
        self.port = port
        self.proc: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def available(self) -> tuple[bool, str]:
        """检查引擎与模型是否就绪。"""
        if find_server() is None:
            return False, "未找到内嵌推理引擎（llama-server.exe）"
        if find_model(self.settings) is None:
            return False, "未找到内置模型文件（.gguf）"
        return True, "就绪"

    def start(self, timeout: int = 300) -> str:
        """启动内嵌推理服务，返回 base_url。已运行则直接复用。"""
        if self.proc and self.proc.poll() is None:
            return self.base_url
        # 已被其它实例占用时直接复用
        if self._healthy():
            return self.base_url

        exe = find_server()
        model = find_model(self.settings)
        if exe is None or model is None:
            raise RuntimeError("内嵌引擎或模型缺失，无法启动本地模式")
        self.proc = subprocess.Popen(
            [str(exe), "-m", str(model),
             "--host", "127.0.0.1", "--port", str(self.port),
             "-c", "4096", "--jinja"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # 等待模型加载完成
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._healthy():
                return self.base_url
            if self.proc.poll() is not None:
                raise RuntimeError("llama-server 启动失败（进程已退出）")
            time.sleep(1)
        raise RuntimeError("本地模型加载超时")

    def _healthy(self) -> bool:
        try:
            r = requests.get(f"http://127.0.0.1:{self.port}/health", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc = None
