# -*- coding: utf-8 -*-
"""
Android APK 导出模块
====================
Windows 本身没有 Android 构建工具链，因此通过 **WSL2 + buildozer** 构建 APK。

流程：
  1. 检测 WSL2 发行版；没有则由界面提示用户执行 `wsl --install`。
  2. 以 root 在 WSL 内安装 buildozer 及其 apt 依赖（首次较慢）。
  3. 生成 main.py + buildozer.spec，复制到 WSL 家目录（避免 /mnt 磁盘性能问题）。
  4. 执行 `buildozer android debug`，把生成的 apk 复制回 Windows 目标目录。

注意：Android 界面需要 Kivy 编写，PyQt6 桌面代码打包后无法显示界面，
      由调用方在导出前做提示。
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

# buildozer 在 Ubuntu 下需要的系统依赖
WSL_DEPS = (
    "git zip unzip curl patch automake openjdk-17-jdk python3-pip autoconf "
    "libtool pkg-config zlib1g-dev libncurses-dev libtinfo6 cmake ccache "
    "libffi-dev libssl-dev libltdl-dev python3-dev python3-venv"
)

# python-for-android 的源码位置与备用下载通道
# GitHub 在许多网络环境下无法直连，改用 codeload 压缩包绕过 git clone
P4A_DIR = "/opt/incode-p4a"
P4A_TARBALL = "https://codeload.github.com/kivy/python-for-android/tar.gz/refs/heads/master"
P4A_DEPS = (
    "appdirs 'colorama>=0.3.3' jinja2 'sh>=2,<3.0' meson ninja build toml "
    "packaging setuptools 'wheel<=0.46.3'"
)

BUILDOZER_SPEC = """[app]
title = {title}
package.name = {package}
package.domain = org.incode
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = {requirements}
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.accept_sdk_license = True
{p4a_source}
[buildozer]
log_level = 2
warn_on_root = 0
"""

# import 名 → PyPI 包名（名称不一致的常见库）
_PIP_NAME = {
    "cv2": "opencv",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "dateutil": "python-dateutil",
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_STDLIB = getattr(sys, "stdlib_module_names", set())

# 桌面专用模块：Android 上没有对应实现，写进 requirements 会直接导致打包失败
_DESKTOP_ONLY = {
    "__future__", "PyQt6", "PyQt5", "PySide6", "PySide2", "tkinter",
    "winreg", "msvcrt", "_winapi", "win32api", "win32con", "win32gui",
}


def requirements_for(code: str) -> str:
    """从代码 import 推导 buildozer requirements（kivy + 第三方库）。

    Android 上没有已安装的第三方库，漏写会直接导致 APK 启动崩溃；
    反之把桌面专用库写进去会让 buildozer 构建失败，两者都要排除。
    """
    mods = set()
    for m in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_]\w*)", code, re.M):
        name = m.group(1)
        if name == "kivy" or name in _STDLIB or name in _DESKTOP_ONLY:
            continue
        mods.add(_PIP_NAME.get(name, name))
    return ",".join(["python3", "kivy"] + sorted(mods))


def _decode(data: bytes) -> str:
    """wsl.exe 的输出可能是 UTF-16LE（-l 系列）或 UTF-8（bash 输出）。"""
    if not data:
        return ""
    if data.count(b"\x00") > len(data) // 4:
        return data.decode("utf-16-le", errors="ignore")
    return data.decode("utf-8", errors="replace")


def wsl_distros() -> list[str]:
    """返回已安装的 WSL 发行版名称列表；未安装 WSL 时返回空列表。"""
    try:
        proc = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True,
                              timeout=40, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return []
    names = []
    for line in _decode(proc.stdout).replace("\x00", "").splitlines():
        name = line.strip()
        if name and not name.startswith("Windows"):
            names.append(name)
    return names


def wsl_installed() -> bool:
    return bool(wsl_distros())


def install_wsl() -> tuple[bool, str]:
    """以管理员权限启动 `wsl --install`（UAC 提权，立即返回）。

    返回 (是否成功发起, 说明文字)。安装完成后通常需要重启系统。
    """
    ps = ("Start-Process -FilePath 'wsl.exe' -ArgumentList '--install' "
          "-Verb RunAs")
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                              capture_output=True, timeout=300,
                              creationflags=_NO_WINDOW)
    except subprocess.SubprocessError as e:
        return False, f"启动失败：{e}"
    if proc.returncode != 0:
        msg = _decode(proc.stderr).strip() or "用户取消了管理员授权"
        return False, msg
    return True, "已启动 WSL2 安装（首次下载约 1~2 GB，完成后可能需要重启系统）"


def to_wsl_path(win_path: str | Path) -> str:
    """Windows 路径 → WSL 路径（C:\\a\\b → /mnt/c/a/b）。"""
    p = Path(win_path).resolve()
    drive = p.drive.rstrip(":").lower()
    tail = str(p)[len(p.drive):].replace("\\", "/")
    return f"/mnt/{drive}{tail}"


def _wsl_cmd(distro: str, root: bool = True) -> list[str]:
    cmd = ["wsl.exe"]
    if distro:
        cmd += ["-d", distro]
    if root:
        cmd += ["-u", "root"]
    return cmd + ["--", "bash", "-lc"]


def wsl_run(distro: str, script: str, timeout: int = 600, root: bool = True) -> str:
    """执行 WSL 命令并返回合并输出；非零退出码抛 RuntimeError。"""
    proc = subprocess.run(_wsl_cmd(distro, root) + [script], capture_output=True,
                          timeout=timeout, creationflags=_NO_WINDOW)
    out = _decode(proc.stdout) + _decode(proc.stderr)
    if proc.returncode != 0:
        raise RuntimeError(out.strip()[-2000:] or f"命令退出码 {proc.returncode}")
    return out


def wsl_stream(distro: str, script: str, on_line, root: bool = True) -> int:
    """流式执行 WSL 命令，逐行回调，返回退出码。"""
    proc = subprocess.Popen(_wsl_cmd(distro, root) + [script],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=_NO_WINDOW)
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = _decode(raw).rstrip()
        if line:
            on_line(line)
    proc.wait()
    return proc.returncode


def _pip_install(distro: str, packages: str, on_log) -> int:
    """pip 安装；旧版 pip 不认识 --break-system-packages，失败后回退重试。"""
    rc = wsl_stream(distro, f"pip3 install --break-system-packages {packages}", on_log)
    if rc != 0:
        rc = wsl_stream(distro, f"pip3 install {packages}", on_log)
    return rc


def ensure_buildozer(distro: str, on_log) -> None:
    """确保 WSL 内 buildozer 可用（缺失时自动安装依赖，首次较慢）。"""
    found = wsl_run(distro, "command -v buildozer || true", timeout=120)
    if not found.strip():
        on_log("[APK] 首次构建：正在 WSL 内安装 buildozer 及系统依赖，请耐心等待…")
        rc = wsl_stream(
            distro,
            "export DEBIAN_FRONTEND=noninteractive; "
            f"apt-get update -y && apt-get install -y {WSL_DEPS}",
            on_log,
        )
        if rc != 0:
            raise RuntimeError("WSL 内系统依赖安装失败，请检查 WSL 网络后重试")
        if _pip_install(distro, "buildozer cython", on_log) != 0:
            raise RuntimeError("buildozer 安装失败，请检查 WSL 内 pip 网络后重试")


def _tune_git(distro: str) -> None:
    """GitHub 走 HTTP/2 在弱网下容易报 "RPC failed"，降级 HTTP/1.1 更稳。"""
    try:
        wsl_run(distro,
                "git config --global http.version HTTP/1.1; "
                "git config --global http.postBuffer 524288000",
                timeout=60)
    except Exception:
        pass


def ensure_p4a(distro: str, on_log) -> str:
    """准备 python-for-android 源码目录。

    buildozer 默认 git clone github.com，而该域名在大量网络环境下无法直连
    （表现为 git RPC failed / 连接超时），此时改用 codeload 压缩包绕过。
    返回可直接写入 buildozer.spec 的 p4a.source_dir；空串表示交给 buildozer 克隆。
    """
    # 已有缓存直接复用：既省下载时间，也避免每次构建都依赖外网
    cached = wsl_run(distro,
                     f"test -f {P4A_DIR}/setup.py && echo CACHED || echo MISSING",
                     timeout=60)
    if "CACHED" in cached:
        on_log("[APK] 使用已缓存的 python-for-android")
        return P4A_DIR

    try:
        probe = wsl_run(
            distro,
            "timeout 20 git ls-remote --heads "
            "https://github.com/kivy/python-for-android.git >/dev/null 2>&1 "
            "&& echo REACHABLE || echo BLOCKED",
            timeout=90,
        )
    except Exception:
        probe = "BLOCKED"
    if "BLOCKED" not in probe:
        return ""

    on_log("[APK] GitHub 无法直连，改用压缩包通道获取 python-for-android…")
    rc = wsl_stream(
        distro,
        f"if [ ! -f {P4A_DIR}/setup.py ]; then "
        f"rm -rf {P4A_DIR} /tmp/p4a.tar.gz && mkdir -p {P4A_DIR} && "
        f"curl -L --retry 3 --connect-timeout 20 -o /tmp/p4a.tar.gz {P4A_TARBALL} && "
        f"tar xzf /tmp/p4a.tar.gz -C {P4A_DIR} --strip-components=1; "
        f"else echo '[APK] 已缓存 python-for-android，跳过下载'; fi",
        on_log,
    )
    if rc != 0:
        raise RuntimeError(
            "无法获取 python-for-android（GitHub 与备用通道均不可达），"
            "请先在 WSL 内配置可用的网络代理后重试")
    if _pip_install(distro, P4A_DEPS, on_log) != 0:
        raise RuntimeError("python-for-android 依赖安装失败")
    return P4A_DIR


def _warn_network(distro: str, on_log) -> None:
    """首次构建要从 dl.google.com 拉 SDK/NDK，不可达时提前给出可读提示。"""
    try:
        has_sdk = wsl_run(
            distro,
            "test -d ~/.buildozer/android/platform/android-sdk && echo YES || echo NO",
            timeout=60)
        if "YES" in has_sdk:
            return
        code = wsl_run(
            distro,
            "timeout 25 curl -s -o /dev/null -w '%{http_code}' "
            "https://dl.google.com/android/repository/repository2-3.xml",
            timeout=60)
        if code.strip() != "200":
            on_log("[APK] 警告：WSL 内无法访问 dl.google.com，首次构建将无法下载 "
                   "Android SDK/NDK，请为 WSL 配置代理后重试")
    except Exception:
        pass


def build_apk(code: str, out_dir: str, package: str = "incodeapp",
              on_log=None, on_stage=None) -> Path:
    """在 WSL2 中用 buildozer 构建 APK，返回生成的 apk 路径。

    首次构建会自动下载 Android SDK/NDK（数 GB），耗时很长。
    """
    log = on_log or (lambda s: None)
    stage = on_stage or (lambda s: None)

    distros = wsl_distros()
    if not distros:
        raise RuntimeError("未检测到 WSL2，请先安装 WSL2 后再导出 APK")
    distro = distros[0]
    log(f"[APK] 使用 WSL 发行版：{distro}")

    stage("检查构建环境")
    ensure_buildozer(distro, log)
    _tune_git(distro)
    p4a_source = ensure_p4a(distro, log)
    _warn_network(distro, log)

    # 生成工程文件
    tmp = Path(tempfile.mkdtemp(prefix="incode_apk_"))
    (tmp / "main.py").write_text(code, encoding="utf-8")
    (tmp / "buildozer.spec").write_text(
        BUILDOZER_SPEC.format(
            title="IN-code App", package=package,
            requirements=requirements_for(code),
            p4a_source=(f"p4a.source_dir = {p4a_source}" if p4a_source else "")),
        encoding="utf-8")

    # 复制到 WSL 家目录（/mnt 上构建极慢）
    remote = f"/root/incode_apk/{package}"
    stage("准备构建目录")
    wsl_run(distro, f"rm -rf /root/incode_apk/{package} && mkdir -p {remote}", timeout=120)
    wsl_run(distro,
            f"cp '{to_wsl_path(tmp / 'main.py')}' '{to_wsl_path(tmp / 'buildozer.spec')}' {remote}/",
            timeout=120)

    # 构建（首次会下载 Android SDK/NDK）
    stage("正在构建 APK（首次需下载 Android SDK，可能较久）")
    # PEP 668：系统 Python 会拒绝 pip 安装，buildozer 内部要装依赖，必须放行
    # 代理：当 WSL 内 dl.google.com 不可达时（国内常见），可经 Windows 主机代理出网
    proxy = os.environ.get("INCODE_WSL_PROXY", "").strip()
    proxy_export = (
        f"export http_proxy='{proxy}' https_proxy='{proxy}' "
        f"no_proxy='localhost,127.0.0.1' && " if proxy else "")
    rc = wsl_stream(
        distro,
        "export PIP_BREAK_SYSTEM_PACKAGES=1 PIP_ROOT_USER_ACTION=ignore; "
        f"{proxy_export}"
        f"cd {remote} && buildozer android debug",
        log)
    if rc != 0:
        raise RuntimeError("buildozer 构建失败，请查看上方日志")

    stage("回收 APK")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    wsl_run(distro, f"cp {remote}/bin/*.apk '{to_wsl_path(out_dir)}/' || true", timeout=300)
    apks = sorted(Path(out_dir).glob("*.apk"), key=lambda p: p.stat().st_mtime)
    if not apks:
        raise RuntimeError("构建完成但未找到 apk 产物")
    return apks[-1]


class ApkBuildWorker(QThread):
    """后台 APK 构建线程（避免界面卡死）。"""

    log = pyqtSignal(str)
    stage = pyqtSignal(str)
    done = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, code: str, out_dir: str, package: str = "incodeapp", parent=None):
        super().__init__(parent)
        self.code = code
        self.out_dir = out_dir
        self.package = package

    def run(self):
        try:
            path = build_apk(self.code, self.out_dir, self.package,
                             on_log=self.log.emit, on_stage=self.stage.emit)
            self.done.emit(str(path))
        except Exception as e:
            self.error.emit(str(e))
