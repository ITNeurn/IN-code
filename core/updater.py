# -*- coding: utf-8 -*-
"""
在线更新模块
============
针对国内访问 GitHub 不稳定的现实做的韧性设计：

- DNS 抗污染：优先用阿里 DoH 实时解析 GitHub 域名，失败时回退到内置的
  已验证 IP 池，通过 socket.getaddrinfo 补丁生效（TLS 证书校验不受影响）。
- 多线程分块下载：HTTP Range 把文件切成 4 块并行，每块独立重试（指数退避），
  单块失败不影响其他块；服务器不支持 Range 时退化为单线程断点续传。
- 完整性校验：更新包内 manifest.json 记录每个文件的 sha256，
  解压（zip CRC）后再逐文件校验，全部通过才允许替换。
- 安全替换：旧 exe 备份为 .bak，由独立 updater 脚本等主程序退出后替换并重启；
  新程序无法启动时用户可手动改名 .bak 回滚。

仅打包（frozen）版本支持在线更新；源码运行提示 git pull。
"""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from config.settings import APP_VERSION, APP_NAME, APP_DATA_DIR

REPO = "ITNeurn/IN-code"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"

# DoH 服务（阿里 / 腾讯），用于绕过本地 DNS 污染
_DOH = [
    ("https://dns.alidns.com/resolve", {"Accept": "application/dns-json"}),
    ("https://doh.pub/dns-query", {"Accept": "application/dns-json"}),
]
# 已实测可用的兜底 IP（新加坡段）
_FALLBACK_IPS = {
    "github.com": ["20.205.243.168", "140.82.116.3"],
    "api.github.com": ["20.205.243.168", "140.82.116.6"],
    "uploads.github.com": ["20.205.243.161"],
    "objects.githubusercontent.com": ["185.199.108.133", "185.199.109.133",
                                       "185.199.110.133", "185.199.111.133"],
}

_dns_lock = threading.Lock()
_dns_done = False


def _doh_lookup(host: str) -> list[str]:
    """通过 DoH 查询域名 A 记录；全部失败返回空列表。"""
    for url, headers in _DOH:
        try:
            r = requests.get(url, params={"name": host, "type": "A"},
                             headers=headers, timeout=8)
            ips = [a["data"] for a in r.json().get("Answer", [])
                   if a.get("type") == 1]
            if ips:
                return ips
        except Exception:
            continue
    return []


def apply_dns_override():
    """给 GitHub 相关域名打上解析补丁（DoH 优先，兜底 IP 池兜底）。

    只补丁这几个域名，其他域名走系统 DNS；全局只执行一次。
    """
    global _dns_done
    with _dns_lock:
        if _dns_done:
            return
        mapping: dict[str, list[str]] = {}
        for host, fallback in _FALLBACK_IPS.items():
            ips = _doh_lookup(host)
            mapping[host] = ips + [ip for ip in fallback if ip not in ips]

        orig_getaddrinfo = socket.getaddrinfo

        def patched(host, port, family=0, type=0, proto=0, flags=0):
            ips = mapping.get(host)
            if ips:
                return orig_getaddrinfo(ips[0], port, family, type, proto, flags)
            return orig_getaddrinfo(host, port, family, type, proto, flags)

        socket.getaddrinfo = patched
        _dns_done = True


def parse_version(tag: str) -> tuple[int, ...]:
    """'v1.2' / '1.2.1' → (1, 2) / (1, 2, 1)，无法解析的段按 0 计。"""
    parts = []
    for seg in tag.lstrip("vV").split("."):
        digits = "".join(c for c in seg if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_update() -> dict:
    """查询最新 Release。

    返回 {ok, latest, notes, assets:[{name,size,url}], error}；
    latest 比当前版本新时才有实际意义，由调用方判断。
    """
    apply_dns_override()
    try:
        r = requests.get(API_LATEST, timeout=20)
        r.raise_for_status()
        j = r.json()
        return {
            "ok": True,
            "latest": j["tag_name"].lstrip("vV"),
            "notes": j.get("body", ""),
            "assets": [{"name": a["name"], "size": a["size"],
                        "url": a["browser_download_url"]}
                       for a in j.get("assets", [])],
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "latest": "", "notes": "", "assets": [], "error": str(e)}


def find_update_asset(assets: list[dict], version: str) -> dict | None:
    """在资产列表中找 update-{version}.zip。"""
    target = f"update-{version}.zip"
    for a in assets:
        if a["name"] == target:
            return a
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Downloader:
    """多线程分块下载器（Range 并行 + 独立重试 + 断点续传兜底）。"""

    def __init__(self, url: str, dest: Path, threads: int = 4,
                 max_retry: int = 6, on_progress=None):
        self.url = url
        self.dest = Path(dest)
        self.threads = max(1, threads)
        self.max_retry = max_retry
        self.on_progress = on_progress or (lambda done, total: None)
        self._downloaded = 0
        self._lock = threading.Lock()
        self._error: Exception | None = None

    def _tick(self, n: int, total: int):
        with self._lock:
            self._downloaded += n
            self.on_progress(self._downloaded, total)

    def _head(self) -> tuple[int, bool]:
        """返回 (文件大小, 是否支持 Range)。"""
        r = requests.head(self.url, allow_redirects=True, timeout=20)
        r.raise_for_status()
        size = int(r.headers.get("Content-Length", 0))
        return size, r.headers.get("Accept-Ranges", "").lower() == "bytes"

    def _fetch_range(self, start: int, end: int, total: int):
        """下载 [start, end] 区间并写入文件，独立重试。"""
        got = 0
        for attempt in range(self.max_retry):
            if self._error:
                return
            try:
                pos = start + got
                headers = {"Range": f"bytes={pos}-{end}"}
                with requests.get(self.url, headers=headers, stream=True,
                                  timeout=(15, 60)) as r:
                    r.raise_for_status()
                    with open(self.dest, "r+b") as f:
                        f.seek(pos)
                        for chunk in r.iter_content(1 << 16):
                            if self._error:
                                return
                            f.write(chunk)
                            got += len(chunk)
                            self._tick(len(chunk), total)
                if got == end - start + 1:
                    return
            except Exception:
                time.sleep(min(2 ** attempt, 30))
        if got != end - start + 1:
            self._error = IOError(f"分块 {start}-{end} 下载失败")

    def _fetch_single(self, total: int):
        """不支持 Range 时的单线程断点续传。"""
        got = 0
        for attempt in range(self.max_retry):
            try:
                headers = {"Range": f"bytes={got}-"} if got else {}
                with requests.get(self.url, headers=headers, stream=True,
                                  timeout=(15, 60)) as r:
                    r.raise_for_status()
                    mode = "ab" if (got and r.status_code == 206) else "wb"
                    if mode == "wb":
                        got = 0
                        with self._lock:
                            self._downloaded = 0
                    with open(self.dest, mode) as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                            got += len(chunk)
                            self._tick(len(chunk), total)
                return
            except Exception:
                time.sleep(min(2 ** attempt, 30))
        self._error = IOError("下载失败（已达最大重试次数）")

    def start(self) -> Path:
        apply_dns_override()
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        total, can_range = self._head()
        if total <= 0:
            raise IOError("无法获取文件大小")

        if can_range and total > 1 << 20:
            # 预分配文件后并行分块
            with open(self.dest, "wb") as f:
                f.truncate(total)
            step = (total + self.threads - 1) // self.threads
            ts = [threading.Thread(target=self._fetch_range,
                                   args=(i, min(i + step - 1, total - 1), total),
                                   daemon=True)
                  for i in range(0, total, step)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
        else:
            self._fetch_single(total)

        if self._error:
            raise self._error
        if self.dest.stat().st_size != total:
            raise IOError("下载不完整：文件大小不符")
        return self.dest


class UpdateWorker(QThread):
    """后台更新线程：检查 → 下载 → 校验 → 暂存。"""

    progress = pyqtSignal(int, int)       # 已下载字节, 总字节
    stage = pyqtSignal(str)               # 阶段提示
    need_update = pyqtSignal(dict)        # 有新版本（携带 release 信息）
    no_update = pyqtSignal()
    failed = pyqtSignal(str)
    ready = pyqtSignal(Path)              # 更新包已就绪，待重启应用

    def run(self):
        try:
            self.stage.emit("正在检查更新…")
            info = check_update()
            if not info["ok"]:
                self.failed.emit(f"无法连接更新服务器：{info['error']}")
                return
            if parse_version(info["latest"]) <= parse_version(APP_VERSION):
                self.no_update.emit()
                return
            asset = find_update_asset(info["assets"], info["latest"])
            if not asset:
                self.failed.emit(
                    f"新版本 v{info['latest']} 没有增量更新包，请到 Release 页下载完整安装包")
                return
            info["asset"] = asset
            self.need_update.emit(info)   # 由界面确认后调用 download()
        except Exception as e:
            self.failed.emit(str(e))

    def download(self, asset: dict):
        """用户确认后开始下载与校验（仍在后台线程执行）。"""
        try:
            staging = APP_DATA_DIR / "update_staging"
            pkg = staging / "update.zip"
            self.stage.emit("正在下载更新包…")
            dl = Downloader(asset["url"], pkg,
                            on_progress=lambda d, t: self.progress.emit(d, t))
            dl.start()

            self.stage.emit("正在校验更新包…")
            files = verify_package(pkg, staging / "files")
            backup_and_stage(files, Path(sys.executable).parent)
            self.ready.emit(staging)
        except Exception as e:
            self.failed.emit(str(e))


def verify_package(pkg: Path, extract_to: Path) -> dict[str, Path]:
    """解压并校验更新包，返回 {相对路径: 本地文件}。"""
    if extract_to.exists():
        shutil.rmtree(extract_to)
    with zipfile.ZipFile(pkg) as z:          # 解压过程自带 CRC 校验
        z.extractall(extract_to)
    manifest = json.loads((extract_to / "manifest.json").read_text(encoding="utf-8"))
    out: dict[str, Path] = {}
    for rel, expect in manifest["files"].items():
        p = extract_to / rel
        if not p.exists():
            raise IOError(f"更新包缺少文件：{rel}")
        if _sha256(p) != expect:
            raise IOError(f"文件校验失败：{rel}")
        out[rel] = p
    return out


def backup_and_stage(files: dict[str, Path], install_dir: Path):
    """把将被覆盖的旧文件备份为 .bak（回滚用）。"""
    for rel in files:
        old = install_dir / rel
        if old.exists():
            shutil.copy2(old, old.with_suffix(old.suffix + ".bak"))


def apply_and_restart(staging: Path):
    """生成 updater 脚本并启动，随后退出主程序。

    updater 等待主进程退出 → 复制新文件 → 重新拉起主程序。
    """
    install_dir = Path(sys.executable).parent
    bat = staging / "updater.bat"
    bat.write_text(
        "@echo off\r\n"
        "set PID=%~1\r\n"
        ":wait\r\n"
        'tasklist /FI "PID eq %PID%" | find "%PID%" >nul\r\n'
        "if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait)\r\n"
        f'xcopy /E /Y /Q "{staging / "files"}\\*" "{install_dir}\\"\r\n'
        f'start "" "{install_dir / (APP_NAME + ".exe")}"\r\n',
        encoding="gbk")  # bat 用系统 ANSI 编码，避免中文路径乱码
    subprocess.Popen(["cmd", "/c", str(bat), str(os.getpid())],
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    sys.exit(0)


def build_update_package(dist_dir: Path, out: Path, version: str):
    """构建 update-{version}.zip：含 exe、资源与内置 C/C++ 工具链，不含模型。"""
    dist_dir = Path(dist_dir)
    include = [dist_dir / f"{APP_NAME}.exe"]
    # assets 为界面资源；runtime/toolchain 为内置 gcc/g++；runtime/python 为内置
    # Python 运行时，增量更新都必须带上，否则老版本用户升级后仍无法运行对应语言
    for sub in ("assets", "runtime/toolchain", "runtime/python"):
        base = dist_dir / "_internal" / sub
        if base.exists():
            include += [p for p in base.rglob("*") if p.is_file()]
    manifest = {"version": version, "files": {}}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in include:
            rel = p.relative_to(dist_dir).as_posix()
            z.write(p, rel)
            manifest["files"][rel] = _sha256(p)
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
    return out
