# -*- coding: utf-8 -*-
"""
项目文件模块
============
自定义项目文件格式 *.incode，严格遵循《AI模式导出文件保存格式.txt》：
    代码类型（隐藏）
    用户自然语言代码
    AI翻译后代码（隐藏）

实际文件结构（纯文本，带分区标记）：
    [IN-code Project v1]
    [代码类型（隐藏）]
    python
    [用户自然语言代码]
    ...用户描述...
    [AI翻译后代码（隐藏）]
    ...生成的代码...

"隐藏"含义：这两个分区对用户只读折叠，仅软件内部解析使用；
用普通文本编辑器打开文件时依然可见文本，但软件界面不展示分区标题含义。
兼容旧版 JSON 格式：首字符为 '{' 时按 JSON 解析；
兼容旧版 .ccproj 扩展名与 [CreativeCoder Project v1] 头标记。
"""
import json
from pathlib import Path

PROJECT_EXT = ".incode"

# 支持的语言与源码扩展名映射
LANG_EXT = {"python": ".py", "c": ".c", "cpp": ".cpp", "java": ".java", "h5": ".html"}
LANG_NAMES = {"python": "Python", "c": "C", "cpp": "C++", "java": "Java", "h5": "H5"}

# 分区标记
MARK_HEADER = "[IN-code Project v1]"
MARK_HEADER_LEGACY = "[CreativeCoder Project v1]"
MARK_LANG = "[代码类型（隐藏）]"
MARK_DESC = "[用户自然语言代码]"
MARK_CODE = "[AI翻译后代码（隐藏）]"


class Project:
    """一个项目 = 自然语言描述 + AI 生成代码 + 语言类型。"""

    def __init__(self, language="python", description="", generated_code=""):
        self.language = language
        self.description = description
        self.generated_code = generated_code
        self.path: Path | None = None

    # ------------------------------------------------------------ 序列化
    def to_text(self) -> str:
        """序列化为 .ccproj 文本格式。"""
        return (
            f"{MARK_HEADER}\n"
            f"{MARK_LANG}\n{self.language}\n"
            f"{MARK_DESC}\n{self.description}\n"
            f"{MARK_CODE}\n{self.generated_code}\n"
        )

    @classmethod
    def from_text(cls, text: str):
        """解析 .ccproj 文本；旧版 JSON 自动兼容。"""
        text = text.lstrip("﻿")
        if text.lstrip().startswith("{"):
            data = json.loads(text)
            return cls(
                language=data.get("code_type", "python"),
                description=data.get("description", ""),
                generated_code=data.get("generated_code", ""),
            )
        lang, desc, code = "python", "", ""
        section = None
        buf = {"lang": [], "desc": [], "code": []}
        for line in text.splitlines():
            if line == MARK_LANG:
                section = "lang"; continue
            if line == MARK_DESC:
                section = "desc"; continue
            if line == MARK_CODE:
                section = "code"; continue
            if line in (MARK_HEADER, MARK_HEADER_LEGACY):
                continue
            if section:
                buf[section].append(line)
        if buf["lang"]:
            lang = buf["lang"][0].strip() or "python"
        # 去掉各分区结尾多余空行
        description = "\n".join(buf["desc"]).rstrip("\n")
        code = "\n".join(buf["code"]).rstrip("\n")
        return cls(language=lang, description=description, generated_code=code)

    # ------------------------------------------------------------ 文件读写
    def save(self, path: str | Path | None = None):
        """保存项目到 .ccproj 文件。无写入权限时抛出 OSError 供界面弹窗提示。"""
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("未指定保存路径")
        target.write_text(self.to_text(), encoding="utf-8")
        self.path = target

    @classmethod
    def load(cls, path: str | Path):
        """从 .ccproj 文件加载项目。"""
        text = Path(path).read_text(encoding="utf-8")
        proj = cls.from_text(text)
        proj.path = Path(path)
        return proj
