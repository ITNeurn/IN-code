# -*- coding: utf-8 -*-
"""
主窗口
======
- 顶部导航栏（两种模式共用）：
  退出AI模式/进入AI模式｜库安装｜文件｜终端｜AI设置｜编程语言｜导出｜模型管理｜Github｜运行｜设置
- 中部：QStackedWidget 承载 AI 模式页 / 传统模式页，一键互相切换。
- 底部：共享终端停靠面板（显示程序运行输出日志）。
"""
import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QComboBox, QStackedWidget, QMenu,
                             QFileDialog, QMessageBox, QInputDialog, QDialog,
                             QDockWidget, QLabel, QLineEdit, QRadioButton,
                             QDialogButtonBox, QFormLayout)

from config.settings import Settings, APP_NAME, APP_VERSION
from core.project import Project, PROJECT_EXT, LANG_EXT, LANG_NAMES
from core.ai_client import AIWorker, ChatWorker
from core.compiler import RunWorker
from core.library_installer import LibraryInstallWorker
from core.exporter import export_source, export_exe
from core.android_exporter import ApkBuildWorker, wsl_installed, install_wsl
from .ai_mode import AIModePage
from .traditional_mode import TraditionalModePage
from .settings_dialog import SettingsDialog
from .widgets.terminal import TerminalPanel
from .widgets.styles import GLOBAL_QSS
from .dialogs.status_dialogs import (CompileDialog, LibraryInstallDialog,
                                     UnderstandFailureDialog)


# ================================================================ 模型管理对话框
class ModelDialog(QDialog):
    """模型管理 / 模型接口编辑：切换云端API模式 / 本地Ollama模式，编辑接口与模型名。"""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("模型管理")
        self.resize(480, 260)

        lay = QVBoxLayout(self)
        form = QFormLayout()

        # 模式切换
        row = QHBoxLayout()
        self.rb_cloud = QRadioButton("云端 DeepSeek API")
        self.rb_local = QRadioButton("本地 Ollama 模型")
        self.rb_cloud.setChecked(settings.get("model_mode") != "local")
        self.rb_local.setChecked(settings.get("model_mode") == "local")
        row.addWidget(self.rb_cloud)
        row.addWidget(self.rb_local)
        row.addStretch(1)
        form.addRow("模型模式", row)

        self.edit_base = QLineEdit(settings.get("api_base"))
        self.edit_cloud = QLineEdit(settings.get("cloud_model"))
        self.edit_host = QLineEdit(settings.get("ollama_host"))
        self.edit_local = QLineEdit(settings.get("local_model"))
        form.addRow("云端接口地址", self.edit_base)
        form.addRow("云端模型名", self.edit_cloud)
        form.addRow("Ollama 服务地址", self.edit_host)
        form.addRow("本地模型名", self.edit_local)
        lay.addLayout(form)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._save)
        box.rejected.connect(self.reject)
        lay.addWidget(box)

    def _save(self):
        s = self.settings
        s.set("model_mode", "local" if self.rb_local.isChecked() else "cloud")
        s.set("api_base", self.edit_base.text().strip())
        s.set("cloud_model", self.edit_cloud.text().strip())
        s.set("ollama_host", self.edit_host.text().strip())
        s.set("local_model", self.edit_local.text().strip())
        self.accept()


# ================================================================ 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.project = Project(language=self.settings.get("language", "python"))

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1180, 760)
        self.setStyleSheet(GLOBAL_QSS)

        # ---------------- 工作线程引用（防止被回收）
        self._ai_worker: AIWorker | None = None
        self._run_worker: RunWorker | None = None
        self._lib_worker: LibraryInstallWorker | None = None
        self._chat_worker: ChatWorker | None = None
        self._apk_worker: ApkBuildWorker | None = None
        self._animating = False   # 模式切换动画进行中标志（防连点）
        self._lib_retry = 0       # AI 请求装库后自动重试翻译的轮数（防死循环）

        # ---------------- 页面
        self.ai_page = AIModePage()
        self.trad_page = TraditionalModePage()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.ai_page)
        self.stack.addWidget(self.trad_page)

        # ---------------- 中央区域 = 导航栏 + 页面栈
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(8, 6, 8, 4)
        cl.setSpacing(4)
        cl.addLayout(self._build_navbar())
        cl.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        # ---------------- 底部终端停靠面板（仅传统模式默认显示，AI 模式隐藏）
        self.terminal = TerminalPanel()
        dock = QDockWidget("终端", self)
        dock.setObjectName("terminal_dock")
        dock.setWidget(self.terminal)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.terminal_dock = dock
        dock.hide()   # 默认处于 AI 模式：不显示终端

        # ---------------- 页面信号
        self.trad_page.ask_ai.connect(self._on_ask_ai)
        self.trad_page.edit_api.connect(self._open_model_dialog)
        self.trad_page.model_changed.connect(
            lambda m: self.settings.set("local_model", m))

        self._sync_language(self.project.language)

    # ================================================================ 导航栏
    def _nav_btn(self, text, handler, checkable=False) -> QPushButton:
        b = QPushButton(text)
        b.setProperty("nav", True)
        b.setCheckable(checkable)
        b.clicked.connect(handler)
        return b

    def _build_navbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)

        # 模式切换按钮（AI模式显示"退出AI模式"，传统模式显示"进入AI模式"）
        self.btn_mode = self._nav_btn("退出AI模式", self._toggle_mode)
        bar.addWidget(self.btn_mode)

        bar.addWidget(self._nav_btn("库安装", self._install_library))

        # 文件菜单
        self.btn_file = self._nav_btn("文件", lambda: None)
        m = QMenu(self)
        m.addAction("新建", self._file_new)
        m.addAction("打开…", self._file_open)
        m.addAction("保存", self._file_save)
        m.addAction("另存为…", lambda: self._file_save(save_as=True))
        self.btn_file.setMenu(m)
        bar.addWidget(self.btn_file)

        bar.addWidget(self._nav_btn("终端", self._toggle_terminal))
        bar.addWidget(self._nav_btn("AI设置", self._open_ai_settings))

        # 编程语言切换
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "C", "C++", "Java", "H5"])
        self.lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        bar.addWidget(self.lang_combo)

        # 导出菜单
        self.btn_export = self._nav_btn("导出", lambda: None)
        em = QMenu(self)
        em.addAction("导出源码…", self._export_source)
        em.addAction("打包为 exe…", self._export_exe)
        em.addAction("打包为 APK…", self._export_apk)
        self.btn_export.setMenu(em)
        bar.addWidget(self.btn_export)

        bar.addWidget(self._nav_btn("模型管理", self._open_model_dialog))
        bar.addWidget(self._nav_btn(
            "Github", lambda: webbrowser.open(self.settings.get("github_url"))))

        bar.addStretch(1)

        self.btn_run = QPushButton("运行 ▶")
        self.btn_run.setProperty("primary", True)
        self.btn_run.clicked.connect(self._run)
        bar.addWidget(self.btn_run)

        bar.addWidget(self._nav_btn("设置", self._open_settings))
        return bar

    # ================================================================ 模式切换
    def _toggle_mode(self):
        """AI 模式与传统模式一键互相切换，带淡入淡出过渡动画，代码双向同步。"""
        if self._animating:
            return
        going_to_trad = self.stack.currentWidget() is self.ai_page
        old_page, new_page = ((self.ai_page, self.trad_page) if going_to_trad
                              else (self.trad_page, self.ai_page))
        # 代码双向同步
        new_page.set_code(old_page.code())

        self._animating = True
        self.btn_mode.setEnabled(False)

        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        from PyQt6.QtWidgets import QGraphicsOpacityEffect

        # 第一阶段：当前页淡出
        eff_out = QGraphicsOpacityEffect(old_page)
        old_page.setGraphicsEffect(eff_out)
        self._fade_out = QPropertyAnimation(eff_out, b"opacity", self)
        self._fade_out.setDuration(180)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def _switch():
            old_page.setGraphicsEffect(None)     # 摘除效果，避免残留
            self.stack.setCurrentWidget(new_page)
            if going_to_trad:
                self.btn_mode.setText("进入AI模式")
                self.terminal_dock.show()
            else:
                self.btn_mode.setText("退出AI模式")
                self.terminal_dock.hide()
            # 第二阶段：新页淡入
            eff_in = QGraphicsOpacityEffect(new_page)
            new_page.setGraphicsEffect(eff_in)
            self._fade_in = QPropertyAnimation(eff_in, b"opacity", self)
            self._fade_in.setDuration(220)
            self._fade_in.setStartValue(0.0)
            self._fade_in.setEndValue(1.0)
            self._fade_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self._fade_in.finished.connect(self._anim_done)
            self._fade_in.start()

        self._fade_out.finished.connect(_switch)
        self._fade_out.start()

    def _anim_done(self):
        """动画结束：清理特效、恢复按钮。"""
        for page in (self.ai_page, self.trad_page):
            page.setGraphicsEffect(None)
        self._animating = False
        self.btn_mode.setEnabled(True)

    # ================================================================ 文件
    def _file_new(self):
        self.project = Project(language=self._current_lang())
        self.ai_page.set_description("")
        self.ai_page.set_code("")
        self.trad_page.set_code("")

    def _file_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", f"IN-code 项目 (*{PROJECT_EXT})")
        if not path:
            return
        try:
            self.project = Project.load(path)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "打开失败", str(e))
            return
        self.ai_page.set_description(self.project.description)
        self.ai_page.set_code(self.project.generated_code)
        self.trad_page.set_code(self.project.generated_code)
        self._sync_language(self.project.language)

    def _file_save(self, save_as=False):
        self._collect_project()
        if save_as or self.project.path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存项目", f"untitled{PROJECT_EXT}",
                f"IN-code 项目 (*{PROJECT_EXT})")
            if not path:
                return
            self.project.path = Path(path)
        try:
            self.project.save()
        except PermissionError:
            QMessageBox.critical(self, "保存失败", "没有写入权限，请更换保存位置")
        except OSError as e:
            QMessageBox.critical(self, "保存失败", str(e))

    def _collect_project(self):
        """把界面内容收集进项目对象。"""
        self.project.language = self._current_lang()
        self.project.description = self.ai_page.description()
        code = (self.trad_page.code() if self.stack.currentWidget() is self.trad_page
                else self.ai_page.code())
        self.project.generated_code = code

    # ================================================================ 语言
    def _current_lang(self) -> str:
        return ["python", "c", "cpp", "java", "h5"][self.lang_combo.currentIndex()]

    def _on_lang_changed(self, idx):
        self._sync_language(["python", "c", "cpp", "java", "h5"][idx])

    def _sync_language(self, lang: str):
        self.lang_combo.blockSignals(True)
        self.lang_combo.setCurrentIndex(["python", "c", "cpp", "java", "h5"].index(lang))
        self.lang_combo.blockSignals(False)
        self.ai_page.set_language(lang)
        self.trad_page.set_language(lang)
        self.settings.set("language", lang)
        self.project.language = lang

    # ================================================================ 终端
    def _toggle_terminal(self):
        self.terminal_dock.setVisible(not self.terminal_dock.isVisible())

    # ================================================================ 库安装
    def _install_library(self):
        name, ok = QInputDialog.getText(self, "库安装", "输入要安装的第三方库名：")
        if not ok or not name.strip():
            return
        pkg = name.strip()
        dlg = LibraryInstallDialog(self)
        dlg.set_package(pkg)
        dlg.show()   # 非模态显示，后台安装
        self._lib_worker = LibraryInstallWorker([pkg], self)
        self._lib_worker.progress.connect(dlg.set_package)
        self._lib_worker.one_done.connect(
            lambda p, ok: (dlg.close(),
                           self.terminal.append_line(
                               f"[库安装] {p} {'成功' if ok else '失败'}"),
                           None if ok else QMessageBox.critical(
                               self, "库安装失败",
                               f"库 {p} 下载/安装失败，请检查网络或库名")))
        self._lib_worker.finished_all.connect(lambda _: dlg.close())
        self._lib_worker.start()

    # ================================================================ 设置入口
    def _open_settings(self):
        SettingsDialog(self.settings, self).exec()

    def _open_ai_settings(self):
        SettingsDialog(self.settings, self, initial="API接口管理").exec()

    def _open_model_dialog(self):
        ModelDialog(self.settings, self).exec()

    # ================================================================ 导出
    def _export_source(self):
        self._collect_project()
        lang = self.project.language
        path, _ = QFileDialog.getSaveFileName(
            self, "导出源码", f"main{LANG_EXT[lang]}",
            f"{LANG_NAMES[lang]} 源码 (*{LANG_EXT[lang]})")
        if not path:
            return
        try:
            export_source(self.project.generated_code, lang, path)
            self.terminal.append_line(f"[导出] 源码已导出到 {path}")
        except PermissionError:
            QMessageBox.critical(self, "导出失败", "没有写入权限，请更换导出位置")
        except OSError as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _export_exe(self):
        self._collect_project()
        if self.project.language != "python":
            QMessageBox.information(self, "提示", "只有 Python 项目支持打包为 exe")
            return
        out_dir = QFileDialog.getExistingDirectory(self, "选择 exe 输出目录")
        if not out_dir:
            return
        self.terminal.append_line("[导出] 正在打包 exe（首次需安装 PyInstaller，请稍候）…")
        # 简单起见在后台线程打包
        from PyQt6.QtCore import QThread, pyqtSignal

        class _ExeWorker(QThread):
            done = pyqtSignal(str)
            error = pyqtSignal(str)

            def __init__(self, code, out):
                super().__init__()
                self.code, self.out = code, out

            def run(self):
                try:
                    exe = export_exe(self.code, self.out)
                    self.done.emit(str(exe))
                except Exception as e:
                    self.error.emit(str(e))

        self._exe_worker = _ExeWorker(self.project.generated_code, out_dir)
        self._exe_worker.done.connect(
            lambda p: self.terminal.append_line(f"[导出] exe 已生成：{p}"))
        self._exe_worker.error.connect(
            lambda m: QMessageBox.critical(self, "打包失败", m))
        self._exe_worker.start()

    def _export_apk(self):
        """导出 Android APK（WSL2 + buildozer）；首次使用会引导安装 WSL2。"""
        self._collect_project()
        if self.project.language != "python":
            QMessageBox.information(self, "提示", "只有 Python 项目支持打包为 APK")
            return
        code = self.project.generated_code
        if not code.strip():
            QMessageBox.information(self, "提示", "当前没有可导出的代码")
            return

        # 前置条件：WSL2（Windows 没有 Android 构建工具链）
        if not wsl_installed():
            ret = QMessageBox.question(
                self, "需要安装 WSL2",
                "打包 APK 需要 WSL2（Windows 的 Linux 子系统）。\n\n"
                "安装将下载约 1~2 GB 的 Linux 发行版，可能需要重启电脑。\n"
                "确认后会弹出管理员权限请求。\n\n现在开始安装吗？")
            if ret != QMessageBox.StandardButton.Yes:
                return
            self.terminal_dock.show()
            self.terminal.append_line("[APK] 正在启动 WSL2 安装…")
            ok, msg = install_wsl()
            self.terminal.append_line(f"[APK] {msg}")
            if ok:
                QMessageBox.information(
                    self, "WSL2 安装已启动",
                    "WSL2 安装已开始，可能需要重启电脑。\n"
                    "重启并完成初始化后，回到此菜单再次点击「打包为 APK…」即可继续。")
            else:
                QMessageBox.critical(self, "WSL2 安装失败", msg)
            return

        # Android 界面必须用 Kivy，PyQt6 桌面代码打包后无法显示界面
        if "kivy" not in code.lower():
            ret = QMessageBox.question(
                self, "Android 界面提示",
                "Android 应用界面需要用 Kivy 编写，当前代码中未检测到 Kivy。\n"
                "打包出的 APK 可能无法显示界面或启动后闪退。\n\n仍要继续打包吗？")
            if ret != QMessageBox.StandardButton.Yes:
                return

        out_dir = QFileDialog.getExistingDirectory(self, "选择 APK 输出目录")
        if not out_dir:
            return

        self.terminal_dock.show()
        self.terminal.append_line("[APK] 开始构建（首次需下载 Android SDK，耗时较长）…")
        self._apk_worker = ApkBuildWorker(code, out_dir, "incodeapp", self)
        self._apk_worker.log.connect(self.terminal.append_line)
        self._apk_worker.stage.connect(lambda s: self.terminal.append_line(f"[APK] {s}"))
        self._apk_worker.done.connect(
            lambda p: QMessageBox.information(self, "打包成功", f"APK 已生成：\n{p}"))
        self._apk_worker.error.connect(
            lambda m: QMessageBox.critical(self, "APK 打包失败", m))
        self._apk_worker.start()

    # ================================================================ 运行（编译流程）
    def _run(self):
        """
        AI 模式：弹出编译页面（"开始理解并编写、编译"）→ AI 翻译 → 写入分区2 → 运行。
        传统模式：直接编译/运行编辑器中的代码。
        """
        if self.stack.currentWidget() is self.ai_page:
            desc = self.ai_page.description()
            if not desc:
                QMessageBox.information(self, "提示", "请先在分区1书写自然语言流程描述")
                return
            # 编译状态页面
            self._compile_dlg = CompileDialog(self)
            self._compile_dlg.set_stage("开始理解并编写、编译（AI解析中…）")
            self._compile_dlg.show()
            self._ai_worker = AIWorker(self.settings, desc, self._current_lang(), self)
            self._ai_worker.finished_ok.connect(self._on_ai_done)
            self._ai_worker.start()
        else:
            code = self.trad_page.code()
            if not code.strip():
                QMessageBox.information(self, "提示", "编辑器中没有代码")
                return
            self._start_run(code)

    def _on_ai_done(self, result):
        self._compile_dlg.close()
        if result.error:
            QMessageBox.critical(self, "调用失败", result.error)
            return
        if result.packages:
            # AI 通过 {UNX}…{UNY} 请求安装第三方库：自动安装后重试翻译
            self._auto_install_and_retry(result.packages)
            return
        if not result.ok:
            # 理解故障模板页面（{INX}…{INY} 协议）
            UnderstandFailureDialog(result.fail_reason, self).exec()
            return
        self._lib_retry = 0
        # 写入分区2 + 同步传统编辑器，然后编译运行
        self.ai_page.set_code(result.code)
        self.trad_page.set_code(result.code)
        self.project.generated_code = result.code
        self._start_run(result.code)

    def _auto_install_and_retry(self, packages: list[str]):
        """AI 请求安装第三方库：自动安装后重新翻译（最多 3 轮，防死循环）。"""
        if self._lib_retry >= 3:
            self._lib_retry = 0
            QMessageBox.warning(self, "库安装",
                                "AI 连续多次要求安装库，已停止自动重试，请检查描述后手动安装。")
            return
        self._lib_retry += 1

        names = "、".join(packages)
        self.terminal_dock.show()
        self.terminal.append_line(f"[库安装] AI 请求安装：{names}")
        dlg = LibraryInstallDialog(self)
        dlg.set_package(names)
        dlg.show()

        def _finished(all_ok: bool):
            dlg.close()
            if all_ok:
                self.terminal.append_line("[库安装] 安装完成，正在重新翻译…")
                self._run()
            else:
                self._lib_retry = 0
                QMessageBox.critical(self, "库安装失败",
                                     f"部分库安装失败（{names}），请检查网络或库名后重试")

        self._lib_worker = LibraryInstallWorker(packages, self)
        self._lib_worker.progress.connect(dlg.set_package)
        self._lib_worker.finished_all.connect(_finished)
        self._lib_worker.start()

    def _start_run(self, code: str):
        # 运行后自动弹出终端显示输出（两种模式都弹出）
        self.terminal_dock.show()
        self.terminal.append_line("—— 开始运行 ——")
        self._run_worker = RunWorker(code, self._current_lang(), self)
        self._run_worker.output.connect(self.terminal.append)
        self._run_worker.line_changed.connect(self._on_line_changed)
        self._run_worker.done.connect(
            lambda c: self.terminal.append_line(f"—— 运行结束（退出码 {c}）——"))
        self._run_worker.failed.connect(self._on_run_failed)
        self._run_worker.start()

    def _on_run_failed(self, msg):
        self.terminal.append_line(f"[错误] {msg}")
        QMessageBox.critical(self, "运行失败", msg)

    def _on_line_changed(self, line: int):
        """运行时代码行高亮：同步到传统模式编辑器（AI 模式无代码区）。"""
        self.trad_page.highlight_line(line)

    # ================================================================ 传统模式：向AI提问
    def _on_ask_ai(self, question: str):
        self.terminal_dock.show()
        self.terminal.append_line(f"[提问] {question}")
        self._chat_worker = ChatWorker(self.settings, question, self)
        self._chat_worker.done.connect(
            lambda r: self.terminal.append_line(f"[AI] {r}\n"))
        self._chat_worker.error.connect(
            lambda e: QMessageBox.critical(self, "提问失败", e))
        self._chat_worker.start()

    # ================================================================ 关闭
    def closeEvent(self, event):
        if self._run_worker:
            self._run_worker.stop()
        self.settings.save()
        super().closeEvent(event)
