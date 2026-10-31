# -*- coding: utf-8 -*-
"""
隔离编译 / 运行环境模块
=======================
原则：软件内置隔离运行环境，不污染用户系统环境。
  - Python：在用户数据目录下创建独立 venv（~/.incode/runtime/venv），
            所有第三方库都安装进该 venv。
  - C / C++：优先使用 runtime/toolchain 目录下的内置 gcc/g++；
             找不到时回退到系统 PATH 中的编译器，并给出提示。

运行时代码行高亮：
  - Python：通过 sys.settrace 钩子逐行执行，向标准错误输出行标记 @@CC_LINE:n，
            界面解析标记后高亮当前执行行。
  - C / C++：暂不支持逐行高亮（需要调试器支持），仅展示编译与运行输出。
"""
import os
import shutil
import subprocess
import sys
import sysconfig
import venv
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from config.settings import VENV_DIR, RUNTIME_DIR

LINE_MARK = "@@CC_LINE:"      # 行高亮标记前缀
BUILD_DIR = RUNTIME_DIR / "build"          # C/C++ 编译输出目录
SRC_DIR = RUNTIME_DIR / "src"              # 临时代码存放目录

# 随软件打包的资源根目录（onedir 打包后为 _internal）
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------- 环境探测
def venv_python() -> Path:
    """返回隔离 venv 中的 python 解释器路径；不存在则先创建 venv。"""
    py = VENV_DIR / "Scripts" / "python.exe"
    if not py.exists():
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        # 打包状态下优先使用内置嵌入式 Python 创建 venv，不依赖系统 Python
        if getattr(sys, "frozen", False):
            embedded_dir = BUNDLE_DIR / "runtime" / "python"
            embedded_python = embedded_dir / "python.exe"
            if embedded_python.exists():
                # 嵌入式 Python 没有 venv 模块，直接复制到 venv 目录
                VENV_DIR.mkdir(parents=True, exist_ok=True)
                scripts_dir = VENV_DIR / "Scripts"
                scripts_dir.mkdir(exist_ok=True)
                # 复制 python.exe、python312.dll、python3.dll 和 python312.zip 到 Scripts 目录
                shutil.copy2(embedded_python, scripts_dir / "python.exe")
                shutil.copy2(embedded_dir / "python312.dll", scripts_dir / "python312.dll")
                shutil.copy2(embedded_dir / "python3.dll", scripts_dir / "python3.dll")
                shutil.copy2(embedded_dir / "python312.zip", scripts_dir / "python312.zip")
                # 复制 Lib/site-packages（含 pip）到 venv
                src_site = embedded_dir / "Lib" / "site-packages"
                if src_site.exists():
                    dst_site = VENV_DIR / "Lib" / "site-packages"
                    if dst_site.exists():
                        shutil.rmtree(dst_site)
                    shutil.copytree(src_site, dst_site)
                # 创建 pyvenv.cfg：home 指向 venv 自身，让 Python 在 Scripts 目录找 python312.zip
                (VENV_DIR / "pyvenv.cfg").write_text(
                    "home = " + str(scripts_dir) + "\n"
                    "include-system-site-packages = false\n"
                    "version = 3.12.10\n",
                    encoding="utf-8"
                )
            else:
                builder_python = shutil.which("python") or ""
                if not builder_python:
                    raise RuntimeError("未检测到本机 Python，且未找到内置嵌入式 Python")
                subprocess.run([builder_python, "-m", "venv", str(VENV_DIR)],
                               check=True, capture_output=True)
        else:
            venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    return py


def venv_pip() -> list[str]:
    """返回调用 venv 内 pip 的命令前缀。"""
    return [str(venv_python()), "-m", "pip"]


def toolchain_bin_dirs() -> list[Path]:
    """内置工具链 bin 目录候选列表（打包目录优先，其次用户数据目录）。"""
    return [BUNDLE_DIR / "runtime" / "toolchain" / "bin",
            RUNTIME_DIR / "toolchain" / "bin"]


def find_c_compiler(lang: str) -> str | None:
    """查找 C/C++ 编译器：先找内置 toolchain，再找系统 PATH。"""
    name = "gcc" if lang == "c" else "g++"
    for d in toolchain_bin_dirs():
        exe = d / f"{name}.exe"
        if exe.exists():
            return str(exe)
    return shutil.which(name)   # 系统 PATH（可能为 None）


def find_java() -> tuple[str | None, str | None]:
    """查找 JDK 的 javac 与 java：先 PATH，再 JAVA_HOME。"""
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac and java:
        return javac, java
    home = os.environ.get("JAVA_HOME")
    if home:
        bin_dir = Path(home) / "bin"
        javac = javac or (str(bin_dir / "javac.exe") if (bin_dir / "javac.exe").exists() else None)
        java = java or (str(bin_dir / "java.exe") if (bin_dir / "java.exe").exists() else None)
    return javac, java


def environment_status() -> dict:
    """供界面显示环境状态。"""
    javac, java = find_java()
    return {
        "venv_ready": (VENV_DIR / "Scripts" / "python.exe").exists(),
        "gcc": find_c_compiler("c"),
        "g++": find_c_compiler("cpp"),
        "javac": javac,
        "java": java,
    }


# ---------------------------------------------------------------- Python 行追踪脚本
_TRACE_RUNNER = r'''
import sys, runpy

target = sys.argv[1]
MARK = "@@CC_LINE:"

def tracer(frame, event, arg):
    # 只追踪目标文件本身的行事件，忽略库代码
    if event == "line" and frame.f_code.co_filename == target:
        sys.stderr.write(MARK + str(frame.f_lineno) + "\n")
        sys.stderr.flush()
    return tracer if frame.f_code.co_filename == target else None

sys.settrace(tracer)
try:
    runpy.run_path(target, run_name="__main__")
finally:
    sys.settrace(None)
'''


# ---------------------------------------------------------------- 运行工作线程
class RunWorker(QThread):
    """在后台线程中编译并运行用户代码。

    信号：
      output(str)      程序标准输出 / 错误文本（已剔除行标记）
      line_changed(int)当前执行到的代码行号（仅 Python）
      done(int)        进程结束，参数为退出码（注意不能命名为 finished，会与 QThread 内置信号冲突导致窗口程序崩溃退出）
      failed(str)      环境错误（如无编译器），无法启动运行
    """
    output = pyqtSignal(str)
    line_changed = pyqtSignal(int)
    done = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, code: str, language: str, parent=None):
        super().__init__(parent)
        self.code = code
        self.language = language
        self._proc: subprocess.Popen | None = None

    # ------------------------------------------------------------ 主流程
    def run(self):
        try:
            SRC_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            if self.language == "python":
                self._run_python()
            elif self.language == "java":
                self._run_java()
            elif self.language == "h5":
                self._run_h5()
            else:
                self._run_c()
        except PermissionError:
            self.failed.emit("没有写入权限，无法创建运行目录")
        except Exception as e:
            self.failed.emit(str(e))

    # ------------------------------------------------------------ Python
    def _run_python(self):
        src = SRC_DIR / "main.py"
        src.write_text(self.code, encoding="utf-8")
        runner = SRC_DIR / "_runner.py"
        runner.write_text(_TRACE_RUNNER, encoding="utf-8")
        cmd = [str(venv_python()), "-u", str(runner), str(src)]
        # 强制子进程用 UTF-8 输出，避免中文 Windows 下默认 GBK 与
        # 父进程 utf-8 解码不一致导致乱码
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        self._spawn(cmd, parse_lines=True, env=env)

    # ------------------------------------------------------------ C / C++
    def _run_c(self):
        compiler = find_c_compiler(self.language)
        if not compiler:
            self.failed.emit(
                f"未找到 {('gcc' if self.language == 'c' else 'g++')} 编译器，"
                "请安装内置工具链或配置系统编译器")
            return
        ext = ".c" if self.language == "c" else ".cpp"
        src = SRC_DIR / f"main{ext}"
        src.write_text(self.code, encoding="utf-8")
        exe = BUILD_DIR / "main.exe"
        std = "-std=c17" if self.language == "c" else "-std=c++17"
        # gcc 在 Windows 上无法正确解析含中文的安装前缀，会找不到 stdio.h 等
        # 原生头文件，这里显式把工具链的 include 目录传给编译器
        inc_dir = Path(compiler).parent.parent / "include"
        inc_flags = ["-idirafter", str(inc_dir)] if inc_dir.is_dir() else []
        env = os.environ.copy()
        # 强制英文诊断信息：中文 Windows 下 gcc 报错是 GBK，按 UTF-8 解码会乱码
        env["LANG"] = "C"
        env["LC_ALL"] = "C"
        # 让编译产物能直接运行：静态链接 gcc/c++ 运行库，并把工具链 bin 加进 PATH
        for d in toolchain_bin_dirs():
            if d.exists():
                env["PATH"] = str(d) + os.pathsep + env.get("PATH", "")
                break
        # 先编译
        proc = subprocess.run([compiler, str(src), "-o", str(exe), std, "-O0",
                               "-static-libgcc", "-static-libstdc++", *inc_flags],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=env)
        if proc.returncode != 0:
            self.output.emit("编译失败：\n" + proc.stderr)
            self.done.emit(proc.returncode)
            return
        self.output.emit("编译成功，开始运行……\n")
        self._spawn([str(exe)], parse_lines=False, env=env)

    # ------------------------------------------------------------ Java
    def _run_java(self):
        javac, java = find_java()
        if not (javac and java):
            self.failed.emit(
                "未检测到 JDK（javac/java），请先安装 JDK 17+ 并加入 PATH 或配置 JAVA_HOME")
            return
        src = SRC_DIR / "Main.java"   # public class 名必须与文件名一致
        src.write_text(self.code, encoding="utf-8")
        proc = subprocess.run([javac, "-encoding", "UTF-8", "Main.java"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=str(SRC_DIR))
        if proc.returncode != 0:
            self.output.emit("编译失败：\n" + proc.stderr)
            self.done.emit(proc.returncode)
            return
        self.output.emit("编译成功，开始运行……\n")
        self._spawn([java, "-cp", str(SRC_DIR), "Main"], parse_lines=False)

    # ------------------------------------------------------------ H5
    def _run_h5(self):
        import webbrowser
        page = SRC_DIR / "index.html"
        page.write_text(self.code, encoding="utf-8")
        webbrowser.open(page.as_uri())
        self.output.emit(f"已在默认浏览器中打开：{page}\n")
        self.line_changed.emit(-1)
        self.done.emit(0)

    # ------------------------------------------------------------ 子进程管理
    def _spawn(self, cmd: list[str], parse_lines: bool, env: dict | None = None):
        """启动子进程并实时转发输出；Python 模式下解析行标记。

        env 为 None 时继承当前进程环境；Python 运行会传入强制 UTF-8 的环境变量。
        """
        self._proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(SRC_DIR), env=env,
        )
        assert self._proc.stdout is not None
        for raw in self._proc.stdout:
            if parse_lines and raw.startswith(LINE_MARK):
                try:
                    self.line_changed.emit(int(raw[len(LINE_MARK):].strip()))
                except ValueError:
                    pass
            else:
                self.output.emit(raw)
        code = self._proc.wait()
        self.line_changed.emit(-1)   # 取消高亮
        self.done.emit(code)

    def stop(self):
        """终止正在运行的程序。"""
        if self._proc and self._proc.poll() is None:
            self._proc.kill()
