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

/* 普通按钮 */
QPushButton {
    background: #2c2e33; color: #e8eaed; border: none;
    border-radius: 8px; padding: 6px 14px;
}
QPushButton:hover { background: #3a3d44; }
QPushButton:disabled { background: #24262b; color: #6b7078; }

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

/* 底部终端面板：容器透明，让光场延续到底部 */
QWidget#terminalRoot { background: transparent; }

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

/* ---------------- 华为风格设置卡片（主题设置页） */
QFrame[hcard="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #171a1f, stop:1 #111317);
    border: 1px solid #24272e; border-radius: 16px;
}
QLabel[h1="true"] {
    font-size: 22px; font-weight: bold; color: #ffffff;
}
QLabel[h2="true"] {
    font-size: 15px; font-weight: 600; color: #e8eaed;
}
QLabel[hint="true"] {
    font-size: 12px; color: #8b949e;
}
QLabel[hicon="true"] {
    font-size: 17px; color: #0b0c0e; border-radius: 11px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 #1abc9c, stop:1 #23d1ae);
}

/* 页面根容器透明，让主窗口的光场背景透出（关闭光感时背景为纯黑，观感不变） */
QWidget#pageRoot, QWidget#stage, QWidget#glassPanel, QWidget#themeRoot,
QStackedWidget {
    background: transparent;
}

/* 分段控件（光感强度：弱档 / 均衡档 / 强档） */
QFrame[segbar="true"] {
    background: #1a1d22; border: 1px solid #24272e; border-radius: 11px;
}
QPushButton[seg="true"] {
    background: transparent; color: #8b949e; border: none;
    border-radius: 8px; padding: 7px 0; font-size: 13px;
}
QPushButton[seg="true"]:hover { background: #24272e; color: #c9cdd4; }
QPushButton[seg="true"]:checked {
    background: #2b3038; color: #ffffff; font-weight: bold;
}
QPushButton[seg="true"]:disabled { color: #5a5f68; }
"""

# 沉浸光感开启时追加：控件让出实色底，改为半透明介质，光从背后透出
GLOW_QSS = """
QPushButton { background: rgba(52, 58, 66, 120); }
QPushButton:hover { background: rgba(74, 82, 92, 160); }
QPushButton[nav="true"] { background: rgba(52, 58, 66, 130); }
QPushButton[nav="true"]:hover { background: rgba(74, 82, 92, 165); }
QPlainTextEdit { background: rgba(8, 12, 15, 96); }
QPlainTextEdit[editor="true"] { background: rgba(8, 12, 15, 96); }
QPlainTextEdit[terminal="true"] { background: rgba(8, 10, 12, 140); }
QLineEdit, QComboBox { background: rgba(10, 14, 18, 135); }
QListWidget { background: rgba(10, 14, 18, 130); }
QListWidget[sidebar="true"] { background: rgba(10, 14, 18, 200); }

/* 主题设置卡片改为半透明介质，让页面自身的光场透出 */
QFrame[hcard="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 rgba(23, 26, 31, 150),
                                stop:1 rgba(17, 19, 23, 130));
}
QFrame[segbar="true"] { background: rgba(26, 29, 34, 160); }
"""
