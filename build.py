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

sys.path.insert(0, str(ROOT))
from config.settings import APP_VERSION  # noqa: E402


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
    archive = DIST.parent / f"IN-code-{APP_VERSION}.7z"
    out = DIST.parent / f"IN-code-{APP_VERSION}-sfx.exe"
    subprocess.run([seven_zip, "a", "-t7z", "-mx=1", "-mmt=on",
                    str(archive), "IN-code"], cwd=DIST.parent, check=True)

    # SFX 配置模板里的 {version} 替换为当前版本号
    cfg_text = (ROOT / "sfx_config.txt").read_text(encoding="utf-8")
    tmp_cfg = DIST.parent / "_sfx_config_runtime.txt"
    tmp_cfg.write_text(cfg_text.replace("{version}", APP_VERSION), encoding="utf-8")

    with open(out, "wb") as w:
        for f in (sfx_module, tmp_cfg, archive):
            with open(f, "rb") as r:
                shutil.copyfileobj(r, w, 1 << 20)
    tmp_cfg.unlink(missing_ok=True)
    print("[sfx] 自解压安装包 ->", out)


def build_update():
    """生成增量更新包 update-{version}.zip（只含 exe 与资源，不含模型）。"""
    from core.updater import build_update_package
    out = DIST.parent / f"update-{APP_VERSION}.zip"
    build_update_package(DIST / "IN-code", out, APP_VERSION)
    print("[update] 增量更新包 ->", out)


if __name__ == "__main__":
    build_app()
    if "--installer" in sys.argv:
        build_installer()
    if "--sfx" in sys.argv:
        build_sfx()
    if "--update" in sys.argv:
        build_update()
