# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：目录模式，内置模型/引擎/资源随包分发。"""
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 超能模式进入准备动画
        (str(ROOT / "assets"), "assets"),
        # 内嵌推理引擎 llama.cpp（llama-server.exe 及依赖 dll）
        (r"E:\Doubao\CreativeCoder\runtime\llama", "runtime/llama"),
        # 内置 DeepSeek R1 7B GGUF 模型（约 4.7GB）
        (r"E:\Doubao\CreativeCoder\models", "models"),
    ],
    hiddenimports=["PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["torch", "tensorflow", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts,
    [],
    exclude_binaries=True,
    name="IN-code",
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="IN-code",
)
