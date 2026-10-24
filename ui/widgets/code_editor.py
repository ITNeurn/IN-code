# -*- coding: utf-8 -*-
"""
代码编辑器组件
==============
基于 QPlainTextEdit，提供：
  - 行号栏
  - Python / C / C++ 基础语法高亮
  - 当前执行行高亮（运行时代码行高亮需求）
"""
from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import (QColor, QPainter, QTextFormat, QSyntaxHighlighter,
                         QTextCharFormat, QFont)
from PyQt6.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
import re


# ---------------------------------------------------------------- 语法高亮
class SimpleHighlighter(QSyntaxHighlighter):
    """轻量级语法高亮：关键字、字符串、注释、数字。"""

    KEYWORDS = {
        "python": ["def", "class", "import", "from", "return", "if", "elif",
                   "else", "for", "while", "in", "not", "and", "or", "try",
                   "except", "finally", "with", "as", "pass", "break",
                   "continue", "lambda", "None", "True", "False", "print",
                   "range", "len", "input", "int", "str", "float", "list", "dict"],
        "c": ["int", "char", "float", "double", "void", "if", "else", "for",
              "while", "do", "switch", "case", "break", "continue", "return",
              "struct", "typedef", "include", "define", "sizeof", "const",
              "static", "unsigned", "long", "short", "printf", "scanf", "main"],
    }
    KEYWORDS["cpp"] = KEYWORDS["c"] + ["std", "cout", "cin", "endl", "namespace",
                                       "class", "public", "private", "new",
                                       "delete", "template", "vector", "string"]

    def __init__(self, document, language="python"):
        super().__init__(document)
        self.language = language
        kw = QTextCharFormat()
        kw.setForeground(QColor("#569cd6"))   # 关键字：蓝
        kw.setFontWeight(QFont.Weight.Bold)
        self.fmt_kw = kw
        s = QTextCharFormat(); s.setForeground(QColor("#ce9178")); self.fmt_str = s      # 字符串
        c = QTextCharFormat(); c.setForeground(QColor("#6a9955")); c.setFontItalic(True); self.fmt_cmt = c  # 注释
        n = QTextCharFormat(); n.setForeground(QColor("#b5cea8")); self.fmt_num = n      # 数字

    def highlightBlock(self, text):
        # 关键字
        for word in self.KEYWORDS.get(self.language, []):
            for m in re.finditer(rf"\b{re.escape(word)}\b", text):
                self.setFormat(m.start(), len(word), self.fmt_kw)
        # 数字
        for m in re.finditer(r"\b\d+(\.\d+)?\b", text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_num)
        # 字符串
        for m in re.finditer(r'("[^"\n]*"|\'[^\'\n]*\')', text):
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_str)
        # 注释
        mark = "#" if self.language == "python" else "//"
        idx = text.find(mark)
        if idx >= 0:
            self.setFormat(idx, len(text) - idx, self.fmt_cmt)
        if self.language == "python":
            for m in re.finditer(r'"""[\s\S]*?"""', text):
                pass  # 跨行字符串从简


# ---------------------------------------------------------------- 行号栏
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint(event)


class CodeEditor(QPlainTextEdit):
    """带行号 + 语法高亮 + 执行行高亮的代码编辑器。"""

    def __init__(self, language="python", parent=None):
        super().__init__(parent)
        self.setProperty("editor", True)
        self.language = language
        self.highlighter = SimpleHighlighter(self.document(), language)
        self._exec_line = -1        # 当前执行行（-1 表示无）

        self.line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.update_line_number_area_width(0)

    # ------------------------------------------------------------ 语言
    def set_language(self, language: str):
        self.language = language
        self.highlighter = SimpleHighlighter(self.document(), language)
        self.highlighter.rehighlight()

    # ------------------------------------------------------------ 行号栏
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_area.scroll(0, dy)
        else:
            self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_area.setGeometry(QRect(cr.left(), cr.top(),
                                         self.line_number_area_width(), cr.height()))

    def line_number_area_paint(self, event):
        painter = QPainter(self.line_area)
        painter.fillRect(event.rect(), QColor("#1e1f24"))
        block = self.firstVisibleBlock()
        num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor("#888888"))
                painter.drawText(0, top, self.line_area.width() - 5,
                                 self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            num += 1

    # ------------------------------------------------------------ 执行行高亮
    def highlight_exec_line(self, line: int):
        """高亮正在执行的代码行；传 -1 取消高亮。"""
        self._exec_line = line
        self.setExtraSelections(self._build_extra_selections())

    def _build_extra_selections(self):
        selections = []
        if self._exec_line > 0 and self._exec_line <= self.blockCount():
            sel = QTextEdit.ExtraSelection()   # PyQt6 中 ExtraSelection 属于 QTextEdit
            sel.format.setBackground(QColor(26, 188, 156, 70))   # 青绿半透明高亮
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down,
                                cursor.MoveMode.MoveAnchor, self._exec_line - 1)
            sel.cursor = cursor
            selections.append(sel)
        return selections
