# -*- coding: utf-8 -*-
"""全局样式：按 PPT 真实画面还原的深色主题
   - 背景纯黑 #000000 / 深灰面板 #1e1f24
   - 导航按钮深灰圆角 #2c2e33，文字白色
   - 主按钮（运行/确认/激活）青绿色 #1abc9c
   - 弹窗深灰圆角卡片 #26282e
"""

GLOBAL_QSS = """
QMainWindow, QDialog, QWidget { background: #000000; }
QWidget { font-family: "Microsoft YaHei", "微软雅黑"; font-size: 13px; color: #e8eaed; }
QLabel { background: transparent; }

/* 顶部导航按钮：深灰圆角小按钮 */
QPushButton[nav="true"] {
    background: #2c2e33; color: #e8eaed; border: none; border-radius: 9px;
    padding: 6px 13px; min-height: 20px;
}
QPushButton[nav="true"]:hover { background: #3a3d44; }
QPushButton[nav="true"]:checked { background: #1abc9c; color: #0b0c0e; }

/* 主按钮（运行 ▶ / 确认 / 激活）：青绿色 */
QPushButton[primary="true"] {
    background: #1abc9c; color: #0b0c0e; border: none; border-radius: 9px;
    padding: 7px 18px; font-weight: bold;
}
QPushButton[primary="true"]:hover { background: #23d1ae; }
QPushButton[primary="true"]:disabled { background: #4a4d55; color: #888; }

/* 危险 / 关闭按钮 */
QPushButton[danger="true"] {
    background: #e74c3c; color: #ffffff; border: none; border-radius: 9px;
    padding: 7px 18px; font-weight: bold;
}
QPushButton[danger="true"]:hover { background: #ff6152; }

/* 工作区面板：深灰圆角卡片 */
QFrame[panel="true"] {
    background: #1e1f24; border: 1px solid #2c2e33; border-radius: 12px;
}

/* 终端：近黑 + 绿色字 */
QPlainTextEdit[terminal="true"] {
    background: #111216; color: #7ee787; border: 1px solid #2c2e33;
    border-radius: 8px; font-family: Consolas, "Courier New"; font-size: 12px;
}

/* 代码编辑器：深色代码区 */
QPlainTextEdit[editor="true"] {
    background: #16171c; color: #e8eaed; border: none; border-radius: 6px;
    font-family: Consolas, "Courier New"; font-size: 13px;
    selection-background-color: #1abc9c;
}
QPlainTextEdit { background: #16171c; color: #e8eaed; border: none; }

/* 设置侧边栏 */
QListWidget[sidebar="true"] {
    background: #1e1f24; border: none; border-right: 1px solid #2c2e33; outline: none;
}
QListWidget[sidebar="true"]::item { padding: 10px 14px; color: #c9cdd4; }
QListWidget[sidebar="true"]::item:selected {
    background: #26282e; color: #1abc9c; border-left: 3px solid #1abc9c;
}
QListWidget { background: #16171c; color: #e8eaed; border: 1px solid #2c2e33; border-radius: 6px; }

QLineEdit, QComboBox {
    background: #16171c; color: #e8eaed; border: 1px solid #2c2e33;
    border-radius: 6px; padding: 5px 8px;
}
QLineEdit:focus, QComboBox:focus { border-color: #1abc9c; }
QComboBox QAbstractItemView { background: #26282e; color: #e8eaed; }

QMenu { background: #26282e; color: #e8eaed; border: 1px solid #3a3d44; }
QMenu::item:selected { background: #1abc9c; color: #0b0c0e; }

QSplitter::handle { background: #2c2e33; }
QProgressBar { background: #2c2e33; border-radius: 6px; text-align: center; color: #e8eaed; }
QProgressBar::chunk { background: #1abc9c; border-radius: 6px; }
QMessageBox { background: #1e1f24; }
QRadioButton { color: #e8eaed; }
QDockWidget { color: #e8eaed; }
"""
