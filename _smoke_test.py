# -*- coding: utf-8 -*-
"""冒烟测试：不进入事件循环，实例化各页面/对话框并验证页面流转逻辑。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

app = QApplication([])

from config.settings import Settings
from ui.main_window import MainWindow, ModelDialog
from ui.settings_dialog import SettingsDialog, MENU
from ui.dialogs.status_dialogs import (CompileDialog, LibraryInstallDialog,
                                       UnderstandFailureDialog)
from ui.dialogs.super_mode_wizard import (WarningDialog1, WarningDialog2,
                                          WarningDialog3, LibDirDialog,
                                          MoeChoiceDialog, FinishDialog)
from core.project import Project

failures = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    if not cond:
        failures.append(name)


def toggle(win):
    """切换模式并等待淡入淡出动画完成。"""
    import time
    win._toggle_mode()
    for _ in range(100):
        app.processEvents()
        if not win._animating:
            return
        time.sleep(0.02)


# ---------------- 主窗口与双模式
win = MainWindow()
check("默认进入AI模式", win.stack.currentWidget() is win.ai_page)
check("导航按钮文字=退出AI模式", win.btn_mode.text() == "退出AI模式")

toggle(win)
check("切换到传统模式", win.stack.currentWidget() is win.trad_page)
check("导航按钮文字=进入AI模式", win.btn_mode.text() == "进入AI模式")

# 代码双向同步
win.trad_page.set_code("print(1)")
toggle(win)
check("传统→AI 代码同步", win.ai_page.code() == "print(1)")
win.ai_page.set_code("print(2)")
toggle(win)
check("AI→传统 代码同步", win.trad_page.code() == "print(2)")

# 语言切换
win.lang_combo.setCurrentIndex(1)   # C
check("语言切换为C", win._current_lang() == "c")
check("编辑器语言同步", win.trad_page.code_edit.language == "c")
win.lang_combo.setCurrentIndex(0)

# ---------------- 项目文件保存/加载
toggle(win)  # 回到AI模式
win.ai_page.set_description("1. 输入n 2. 输出1..n的累加和")
win.ai_page.set_code("n=int(input())\nprint(sum(range(1,n+1)))")
win._collect_project()
tmp = os.path.join(os.path.dirname(__file__), "_test_proj.ccproj")
win.project.save(tmp)
p2 = Project.load(tmp)
check("项目文件保存/加载",
      p2.description.startswith("1.") and "sum" in p2.generated_code
      and p2.language == "python")
# 新格式：分区标记文本（代码类型/生成代码为隐藏分区）
raw = open(tmp, encoding="utf-8").read()
check("代码类型分区", "[代码类型（隐藏）]" in raw)
check("自然语言明文可见", "累加" in raw)
check("生成代码分区", "[AI翻译后代码（隐藏）]" in raw)
os.remove(tmp)

# ---------------- 设置对话框六页面
dlg = SettingsDialog(win.settings, win)
check("设置菜单6项", dlg.menu.count() == 6)
dlg.menu.setCurrentRow(1)
check("切换到API接口管理页", dlg.stack.currentIndex() == 1)
dlg2 = SettingsDialog(win.settings, win, initial="API接口管理")
check("AI设置直达API页", dlg2.stack.currentIndex() == 1)

# ---------------- 状态弹窗
c = CompileDialog(win)
check("编译弹窗文字", "开始理解并编写、编译" in c.label.text())
l = LibraryInstallDialog(win)
l.set_package("numpy")
check("库安装弹窗动态库名", "numpy" in l.label.text())
u = UnderstandFailureDialog("缺少循环条件", win)
check("理解故障弹窗", u.btn_back.text() == "返回修改描述")

# ---------------- 超能模式向导各页面实例化
for cls in (WarningDialog1, WarningDialog2, WarningDialog3, FinishDialog):
    d = cls(win)
    check(f"{cls.__name__} 实例化", d is not None)
ld = LibDirDialog(win, r"C:\incode_libs")
check("库目录选择页默认值", ld.selected_dir() == r"C:\incode_libs")
md = MoeChoiceDialog(win)
check("MoE页默认为否", md.choice is False)

# ---------------- 模型管理对话框
m = ModelDialog(win.settings, win)
check("模型管理对话框", m.rb_cloud.isChecked() or m.rb_local.isChecked())

# ---------------- 超能模式状态
from core.super_mode import SuperModeManager
mgr = SuperModeManager(win.settings)
check("超能模式默认关闭", not mgr.active)
mgr.activate(r"C:\incode_libs", False)
check("超能模式激活标记", mgr.active)
mgr.deactivate()
check("超能模式关闭", not mgr.active)

print()
print("失败用例:", failures if failures else "无")
sys.exit(1 if failures else 0)
