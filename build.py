# -*- coding: utf-8 -*-
"""一键构建：PyInstaller 打包应用 → （若已装 Inno Setup）编译安装包。

用法：
  python build.py            # 只打包 dist\IN-code
  python build.py --installer# 打包 + 生成安装包（需 Inno Setup 6）
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist" / "IN-code"


def build_app():
    """PyInstaller 目录模式打包。"""
    if DIST.exists():
        shutil.rmtree(DIST)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "IN-code.spec"]
    print("[build]", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)
    print("[build] 应用打包完成 ->", DIST)


def build_installer():
    """调用 Inno Setup 编译安装包。"""
    iscc = None
    for p in (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
              r"C:\Program Files\Inno Setup 6\ISCC.exe",
              r"E:\Doubao\CreativeCoder\tools\InnoSetup6\ISCC.exe"):
        if Path(p).exists():
            iscc = p
            break
    if not iscc:
        print("[installer] 未找到 Inno Setup，请先安装：tools 目录下的 innosetup 安装程序")
        return
    subprocess.run([iscc, "installer.iss"], cwd=ROOT, check=True)
    print("[installer] 安装包生成完成 ->", ROOT / "installer")


def build_sfx():
    """7z 自解压单文件安装包（替代方案，无需 Inno Setup）。"""
    seven_zip = r"C:\Program Files\7-Zip\7z.exe"
    sfx_module = r"C:\Program Files\7-Zip\7z.sfx"
    archive = DIST.parent / "IN-code-1.0.7z"
    out = DIST.parent / "IN-code-1.0-sfx.exe"
    subprocess.run([seven_zip, "a", "-t7z", "-mx=1", "-mmt=on",
                    str(archive), "IN-code"], cwd=DIST.parent, check=True)
    with open(out, "wb") as w:
        for f in (sfx_module, ROOT / "sfx_config.txt", archive):
            with open(f, "rb") as r:
                shutil.copyfileobj(r, w, 1 << 20)
    print("[sfx] 自解压安装包 ->", out)


if __name__ == "__main__":
    build_app()
    if "--installer" in sys.argv:
        build_installer()
    if "--sfx" in sys.argv:
        build_sfx()
