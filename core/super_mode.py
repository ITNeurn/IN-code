# -*- coding: utf-8 -*-
"""
超能模式模块
============
超能模式 = 本地离线能力包：后台下载上百个 Python 第三方库 + 可选 MoE 模型。

下载策略（两阶段，兼顾速度与安全）
--------------------------------
阶段 1  多线程并行下载
        把库清单切成 N 份，每份由独立线程执行
        ``pip download -d <该线程独立缓存目录> <单个库>``。
        下载是纯网络 IO，多线程并行收益最大；每个线程用自己的缓存目录，
        避免多个 pip 进程往同一个目录写 wheel 造成文件损坏。

阶段 2  单进程离线安装
        ``pip install --no-index --find-links=<各线程缓存> --target <库目录> <库清单>``。
        只读写本地 wheel，不再联网，也不会出现多个 pip 进程并发写
        site-packages 的锁冲突。若因个别依赖缺失失败，自动回退为在线安装兜底。

安装位置
--------
库装到用户在第 4 步选择的目录（--target 方式），同时在该隔离 venv 的
site-packages 下写入 ``_incode_super.pth``，使运行用户代码时能直接 import。

MoE 模型
--------
走 ``ollama pull``，逐行解析输出中的百分比实现进度显示；未安装 Ollama 时
跳过并记录原因，不影响第三方库的安装。
"""
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from config.settings import APP_DATA_DIR, VENV_DIR
from .compiler import venv_pip, venv_python

# ---------------------------------------------------------------- 库清单
# 按使用场景分组，便于日志展示与后续扩展（当前共 100+ 个库）
SUPER_PACKAGE_GROUPS = {
    "基础与工具": [
        "tqdm", "rich", "loguru", "click", "typer", "colorama", "termcolor",
        "attrs", "packaging", "wheel", "setuptools", "pip-tools", "six",
        "python-dateutil", "pytz", "pyyaml", "toml", "tomli-w",
    ],
    "数据分析": [
        "numpy", "pandas", "scipy", "scikit-learn", "statsmodels", "polars",
        "pyarrow", "openpyxl", "xlsxwriter", "xlrd", "tabulate", "fastexcel",
        "duckdb", "pyjanitor",
    ],
    "网络与 Web": [
        "requests", "httpx", "aiohttp", "urllib3", "beautifulsoup4", "lxml",
        "html5lib", "pyquery", "flask", "fastapi", "uvicorn", "starlette",
        "jinja2", "websockets", "python-dotenv", "pydantic", "sseclient-py",
        "dnspython", "httpx-sse",
    ],
    "图像与媒体": [
        "pillow", "opencv-python-headless", "imageio", "imageio-ffmpeg",
        "scikit-image", "moviepy", "pydub", "mutagen", "qrcode", "colour",
        "pygame", "svgwrite",
    ],
    "科学计算": [
        "sympy", "networkx", "numba", "mpmath", "sortedcontainers", "h5py",
        "xarray", "zarr", "numpy-financial", "pint",
    ],
    "数据库": [
        "sqlalchemy", "pymysql", "psycopg2-binary", "pymongo", "redis",
        "tinydb", "peewee", "alembic", "sqlite-utils", "duckdb-engine",
    ],
    "测试与质量": [
        "pytest", "pytest-cov", "hypothesis", "coverage", "black", "isort",
        "flake8", "mypy", "ruff", "pylint", "pre-commit", "tox",
    ],
    "GUI 与桌面": [
        "pyqt6", "pyside6", "customtkinter", "pyautogui", "pygetwindow",
        "pystray", "pyperclip", "keyboard", "mouse", "darkdetect",
    ],
    "AI 与机器学习": [
        "transformers", "datasets", "tokenizers", "sentencepiece", "timm",
        "onnx", "onnxruntime", "openai", "tiktoken", "gradio",
        "huggingface-hub", "safetensors", "accelerate",
    ],
    "文档与办公": [
        "python-docx", "python-pptx", "pdfplumber", "pypdf", "reportlab",
        "markdown", "markdownify", "docx2txt", "chardet", "charset-normalizer",
        "tabulate",
    ],
}

# 去重后的完整清单（保持分组顺序）
SUPER_PACKAGES: list[str] = []
for _group in SUPER_PACKAGE_GROUPS.values():
    for _pkg in _group:
        if _pkg not in SUPER_PACKAGES:
            SUPER_PACKAGES.append(_pkg)

# 并行下载线程数（过多会被 PyPI 限流，6 路实测最快）
DOWNLOAD_THREADS = 6

# 下载源：优先国内镜像，失败后回退官方源
MIRROR_INDEX = "https://pypi.tuna.tsinghua.edu.cn/simple"

# MoE 模型（Ollama 模型名）
MOE_MODEL = "deepseek-r1:14b"

# 预估磁盘占用（字节），用于空间检查
SUPER_LIB_ESTIMATE = 9 * 1024 ** 3     # 上百个第三方库约 9GB（含缓存）
MOE_ESTIMATE = 10 * 1024 ** 3          # MoE 模型约 10GB

# Windows 下隐藏子进程黑窗
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def default_super_lib_dir() -> str:
    """默认库安装目录：优先选非系统盘中剩余空间最大的，避免占用 C 盘。"""
    best_root, best_free = "", 0
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        try:
            usage = shutil.disk_usage(root)
        except OSError:
            continue
        if usage.free > best_free:
            best_root, best_free = root, usage.free
    if best_root and best_free >= 20 * 1024 ** 3:
        return str(Path(best_root) / "IN-code" / "super_libs")
    return str(APP_DATA_DIR / "super_libs")


def super_lib_dir(settings) -> Path:
    """返回超能模式库安装目录（未设置时自动选非 C 盘）。"""
    path = (settings.get("super_lib_dir") or "").strip()
    return Path(path) if path else Path(default_super_lib_dir())


def total_package_count() -> int:
    return len(SUPER_PACKAGES)


class SuperModeManager:
    """超能模式状态管理：激活标记、磁盘空间检查、关闭。"""

    def __init__(self, settings):
        self.settings = settings

    @property
    def active(self) -> bool:
        return bool(self.settings.get("super_mode", False))

    def activate(self, lib_dir: str, install_moe: bool):
        self.settings.set("super_mode", True)
        self.settings.set("super_lib_dir", lib_dir)
        self.settings.set("super_moe", install_moe)

    def deactivate(self):
        """关闭超能模式（不删除已下载文件，只关闭状态）。"""
        self.settings.set("super_mode", False)

    # ------------------------------------------------------------ 磁盘检查
    @staticmethod
    def check_disk_space(path: str, need_moe: bool) -> tuple[bool, str]:
        """检查目标磁盘剩余空间是否足够。返回 (是否足够, 提示文字)。"""
        need = SUPER_LIB_ESTIMATE + (MOE_ESTIMATE if need_moe else 0)
        try:
            usage = shutil.disk_usage(Path(path).anchor or path)
        except OSError:
            return False, "无法读取目标磁盘信息"
        if usage.free < need:
            return False, (f"磁盘剩余空间不足：需要约 {need // 1024 ** 3}GB，"
                           f"当前剩余 {usage.free // 1024 ** 3}GB")
        return True, f"空间充足（剩余 {usage.free // 1024 ** 3}GB）"


class SuperDownloadWorker(QThread):
    """超能模式后台下载线程：多线程并行下载第三方库 + 可选 MoE 模型。

    信号：
      progress(int, int, str)   已完成数 / 总数 / 当前动作描述
      log(str)                 详细日志（pip 输出、失败原因等）
      moe_progress(int, str)    MoE 下载百分比（-1 表示非百分比状态）与描述
      finished_all(bool, list)  全部结束（是否全部成功, 失败的库清单）
    """

    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    moe_progress = pyqtSignal(int, str)
    finished_all = pyqtSignal(bool, list)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._lock = threading.Lock()
        self._done = 0
        self._total = len(SUPER_PACKAGES)
        self._ok_pkgs: list[str] = []
        self._failed: list[str] = []
        self._cache_dirs: list[Path] = []
        self._cache_root: Path = APP_DATA_DIR / "super_libs_cache"

    # ------------------------------------------------------------ 主流程
    def run(self):
        all_ok = True
        try:
            lib_dir = super_lib_dir(self.settings)
            lib_dir.mkdir(parents=True, exist_ok=True)
            # wheel 缓存放在库目录同盘，避免占用 C 盘
            self._cache_root = lib_dir.parent / "_wheel_cache"

            self.progress.emit(0, self._total, "正在准备隔离环境")
            venv_python()          # 确保 venv 已就绪（不存在会自动创建）
            self._cache_root.mkdir(parents=True, exist_ok=True)

            # 阶段 1：多线程并行下载
            self.log.emit(f"[阶段 1/2] 并行下载 {self._total} 个库 "
                          f"（{DOWNLOAD_THREADS} 线程）")
            self._parallel_download()

            # 阶段 2：单进程离线安装
            if self._ok_pkgs:
                self.log.emit(f"[阶段 2/2] 离线安装 {len(self._ok_pkgs)} 个库 -> {lib_dir}")
                if not self._offline_install(lib_dir):
                    all_ok = False
                self._write_pth(lib_dir)

            if self._failed:
                self.log.emit("以下库下载失败（可稍后重试）：" + "、".join(self._failed))
                all_ok = False

            # MoE 模型
            if self.settings.get("super_moe"):
                self.log.emit("开始下载 MoE 模型（Ollama）")
                if not self._pull_moe():
                    self.log.emit("MoE 模型下载未完成（可稍后在设置中重试）")
                    all_ok = False

        except Exception as e:                       # noqa: BLE001
            self.log.emit(f"[错误] {e}")
            all_ok = False
        finally:
            self.progress.emit(self._done, self._total, "准备完成")
            self.finished_all.emit(all_ok, list(self._failed))

    # ------------------------------------------------------------ 阶段 1
    def _parallel_download(self):
        """把库清单切成若干批，用线程池并行下载。"""
        chunks = [SUPER_PACKAGES[i::DOWNLOAD_THREADS]
                  for i in range(DOWNLOAD_THREADS)]
        self._cache_dirs = [self._cache_root / f"w{i}" for i in range(DOWNLOAD_THREADS)]
        for d in self._cache_dirs:
            d.mkdir(parents=True, exist_ok=True)

        with ThreadPoolExecutor(max_workers=DOWNLOAD_THREADS) as pool:
            list(pool.map(self._download_batch,
                          [(chunk, self._cache_dirs[i]) for i, chunk in enumerate(chunks)]))

    def _download_batch(self, job):
        chunk, cache_dir = job
        for pkg in chunk:
            ok = self._download_one(pkg, cache_dir)
            with self._lock:
                self._done += 1
                (self._ok_pkgs if ok else self._failed).append(pkg)
                done = self._done
            self.progress.emit(done, self._total,
                               f"正在下载 {pkg}" if ok else f"{pkg} 下载失败")

    def _download_one(self, pkg: str, cache_dir: Path) -> bool:
        """下载单个库的 wheel（含依赖）。先镜像源，失败回退官方源。"""
        base = venv_pip() + [
            "download", pkg, "-d", str(cache_dir),
            "--only-binary=:all:",          # 只取预编译 wheel，避免触发本地编译
            "--timeout", "60", "--retries", "2",
            "--disable-pip-version-check", "--no-input", "--quiet",
        ]
        for index in (MIRROR_INDEX, None):
            cmd = list(base) if index is None else base + ["-i", index]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=1800,
                    creationflags=_CREATE_NO_WINDOW,
                )
                if proc.returncode == 0:
                    return True
                detail = (proc.stderr or proc.stdout or "").strip().splitlines()
                if detail:
                    self.log.emit(f"[{pkg}] {detail[-1][:200]}")
            except Exception as e:                   # noqa: BLE001
                self.log.emit(f"[{pkg}] 下载异常：{e}")
        return False

    # ------------------------------------------------------------ 阶段 2
    def _offline_install(self, lib_dir: Path) -> bool:
        """从本地缓存离线安装；失败则回退在线安装兜底。"""
        links = []
        for d in self._cache_dirs:
            links += ["--find-links", str(d)]
        cmd = venv_pip() + [
            "install", "--no-index", *links,
            "--target", str(lib_dir), "--upgrade",
            "--disable-pip-version-check", "--no-input", "--quiet",
        ] + self._ok_pkgs
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=7200,
                                  creationflags=_CREATE_NO_WINDOW)
            if proc.returncode == 0:
                return True
            self.log.emit("[离线安装失败] 回退在线安装兜底")
        except Exception as e:                       # noqa: BLE001
            self.log.emit(f"[离线安装异常] {e}，回退在线安装")

        # 兜底：在线分批安装（每批 10 个，避免单次命令过长）
        ok = True
        for i in range(0, len(self._ok_pkgs), 10):
            batch = self._ok_pkgs[i:i + 10]
            cmd = venv_pip() + [
                "install", *batch, "--target", str(lib_dir), "--upgrade",
                "-i", MIRROR_INDEX, "--timeout", "60",
                "--disable-pip-version-check", "--no-input", "--quiet",
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=3600,
                                      creationflags=_CREATE_NO_WINDOW)
                if proc.returncode != 0:
                    ok = False
                    self.log.emit(f"[在线安装] 批次失败：{batch[0]} 等 {len(batch)} 个")
            except Exception:                        # noqa: BLE001
                ok = False
        return ok

    # ------------------------------------------------------------ 挂载路径
    @staticmethod
    def _write_pth(lib_dir: Path):
        """在隔离 venv 写 .pth，使该目录加入 sys.path（运行用户代码可 import）。"""
        try:
            sp = VENV_DIR / "Lib" / "site-packages"
            sp.mkdir(parents=True, exist_ok=True)
            (sp / "_incode_super.pth").write_text(str(lib_dir) + "\n", encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------ MoE 模型
    def _pull_moe(self) -> bool:
        """用 ollama pull 下载 MoE 模型，解析输出里的百分比做进度。"""
        ollama = shutil.which("ollama")
        if not ollama:
            self.moe_progress.emit(-1, "未检测到 Ollama，跳过 MoE 模型")
            self.log.emit("未检测到 Ollama，无法下载 MoE 模型")
            return False

        self.moe_progress.emit(0, f"正在拉取 {MOE_MODEL}")
        pct_re = re.compile(r"(\d{1,3})%")
        last_pct = -1
        try:
            proc = subprocess.Popen(
                [ollama, "pull", MOE_MODEL],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                creationflags=_CREATE_NO_WINDOW,
            )
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.replace("\r", "\n").strip()
                if not line:
                    continue
                m = pct_re.search(line)
                if m:
                    pct = min(100, int(m.group(1)))
                    if pct != last_pct:              # 避免高频重复刷新
                        last_pct = pct
                        self.moe_progress.emit(pct, f"正在下载 MoE 模型 {MOE_MODEL}")
                else:
                    self.log.emit(f"[ollama] {line[:180]}")
            code = proc.wait()
            if code == 0:
                self.moe_progress.emit(100, f"{MOE_MODEL} 下载完成")
                return True
            return False
        except Exception as e:                       # noqa: BLE001
            self.log.emit(f"[ollama] 拉取失败：{e}")
            return False
