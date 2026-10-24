# -*- coding: utf-8 -*-
"""
IN-code 入口
==================
运行方式：python main.py

打包（冻结）状态下没有控制台，任何未捕获异常/打印都可能直接静默退出，
因此冻结时把 stdout/stderr 重定向到日志文件，并安装崩溃钩子，
便于定位"运行后软件自动退出"类问题。
"""
import faulthandler
import os
import sys
import threading


def _setup_crash_logging():
    """冻结状态下：重定向输出 + 记录未捕获异常到日志文件。"""
    if not getattr(sys, "frozen", False):
        return
    log_dir = os.path.join(os.path.expanduser("~"), ".incode", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")
    # stdout/stderr 重定向（无控制台时二者为 None，print/异常会炸掉进程）
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file
    faulthandler.enable(log_file)

    def _excepthook(exc_type, exc, tb):
        import traceback
        sys.stderr.write("=== 未捕获异常 ===\n")
        traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
        sys.stderr.flush()
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    def _thread_hook(args):
        import traceback
        sys.stderr.write("=== 线程未捕获异常 ===\n")
        traceback.print_exception(args.exc_type, args.exc_value,
                                  args.exc_traceback, file=sys.stderr)
        sys.stderr.flush()

    threading.excepthook = _thread_hook


def main():
    _setup_crash_logging()
    from PyQt6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName("IN-code")
    win = MainWindow()
    win.show()

    # 自测模式（排查打包版运行崩溃）：--selftest-run
    if "--selftest-run" in sys.argv:
        from PyQt6.QtCore import QTimer
        def step_run():
            win.stack.setCurrentWidget(win.trad_page)   # 直接切传统模式（跳过动画）
            win.trad_page.set_code("print('hello selftest')\nprint(1+1)")
            win._start_run(win.trad_page.code())
        def step_done():
            print("[selftest] 运行完成，软件仍存活")
            sys.stdout.flush()
            QTimer.singleShot(3000, lambda: app.exit(0))   # 3秒后才退出
        win._run_done_once = False
        orig = win.terminal.append_line
        def watch(text):
            orig(text)
            if "运行结束" in text and not win._run_done_once:
                win._run_done_once = True
                step_done()
        win.terminal.append_line = watch
        QTimer.singleShot(1000, step_run)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
