# -*- coding: utf-8 -*-
"""
导出模块
========
两种导出方式：
  1. 导出源码：把 AI 生成的代码保存为对应语言源文件（.py / .c / .cpp）。
  2. 打包 exe：仅 Python 项目支持，通过 PyInstaller 打包为 Windows 可执行文件。
"""
import shutil
import subprocess
from pathlib import Path

from .project import LANG_EXT
from .compiler import venv_python, venv_pip, SRC_DIR


def export_source(code: str, language: str, target_path: str):
    """把源码导出到用户选择的路径。"""
    Path(target_path).write_text(code, encoding="utf-8")


def export_exe(code: str, target_dir: str, name: str = "app") -> Path:
    """把 Python 代码打包为 exe，返回生成的 exe 路径。

    注意：打包耗时较长，调用方需在后台线程执行。
    """
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    src = SRC_DIR / f"{name}.py"
    src.write_text(code, encoding="utf-8")

    py = venv_python()
    # 确保 venv 中装有 pyinstaller
    subprocess.run(venv_pip() + ["install", "pyinstaller"],
                   capture_output=True, timeout=1800)
    cmd = [str(py), "-m", "PyInstaller", "--onefile", "--noconsole",
           "--distpath", target_dir, "--workpath", str(SRC_DIR / "build_exe"),
           "--specpath", str(SRC_DIR), str(src)]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError("打包失败：\n" + proc.stderr[-2000:])
    return Path(target_dir) / f"{name}.exe"
