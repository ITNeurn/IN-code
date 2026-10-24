# IN-code

**用自然语言，写出真代码。**

IN-code 是一款 Windows 桌面编程学习软件（Python + PyQt6 + C）。核心理念是
**"AI 只当翻译器"**：你用自然语言写下逻辑流程，AI 把它翻译成 Python / C / C++
标准源码，而不是生成一个看不懂的黑盒。所有生成的代码都可以打开逐行查看、
编辑、运行，帮助你真正理解每一行代码。

![平台](https://img.shields.io/badge/Windows-10%2B-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-green) ![License](https://img.shields.io/badge/License-MIT-orange)

## 特性

- **双模式界面**
  - **AI 模式**：一个大编辑区，只写自然语言；AI 翻译后的代码在后台保留，
    一键运行。模式切换带平滑过渡动画。
  - **传统模式**：完整的代码编辑器 + 终端输出，运行时逐行高亮当前执行行。
- **云端 + 本地双 AI 后端**
  - 云端：DeepSeek API（OpenAI 兼容接口，可自定义地址）
  - 本地：内嵌 llama.cpp 引擎 + 打包内置的 DeepSeek R1 7B GGUF 模型，
    离线也能用；或连接本机 Ollama
- **理解故障协议**：AI 没听懂你的描述时，返回 `[[理解故障]]` 并给出澄清问题，
  而不是瞎编代码
- **隔离运行环境**：所有代码在用户目录下的独立 venv 中运行，不污染系统
- **超能模式**：六步向导解锁扩展库安装能力（三重警告 → 目录选择 → MoE 询问）
- **自定义项目文件** `.incode`：自然语言描述与生成代码同时保存，纯文本可读
- **导出**：一键导出标准源码，或打包成独立可执行文件

## 下载安装

前往 [Releases](../../releases) 下载：

| 文件 | 说明 |
| --- | --- |
| `IN-code-1.0-sfx.exe.7z.001 ~ .003` | 自解压安装包分卷（内含 DeepSeek R1 7B 模型，全部下载后解压第一个分卷即可） |

> 安装包约 4.4 GB（内置 4.7 GB 本地模型），解压后约需 5 GB 磁盘空间。

不想下载模型？也可以从源码运行，选择"云端 API"模式，只需配置 DeepSeek API Key。

## 从源码运行

```bash
git clone https://github.com/<你的用户名>/IN-code.git
cd IN-code
pip install PyQt6 requests
python main.py
```

首次启动后在 **设置 → API 接口管理** 中填入 DeepSeek API Key，
或切换到 **本地模型** 模式（需要 llama.cpp `llama-server` 与 GGUF 模型，
放到 `~/.incode/runtime/llama` 与 `~/.incode/models`，详见 `core/local_engine.py`）。

## 从源码打包

```bash
pip install pyinstaller
# 修改 IN-code.spec 中 datas 的模型/引擎路径后：
python build.py           # 仅打包 dist\IN-code
python build.py --sfx     # 打包 + 生成 7z 自解压安装包（需 7-Zip）
python build.py --installer  # 打包 + 生成 Inno Setup 安装包（需 Inno Setup 6）
```

## 目录结构

```
IN-code/
├── main.py                 # 程序入口（含崩溃日志与自测模式）
├── config/settings.py      # 全局配置与用户数据目录
├── core/
│   ├── ai_client.py        # DeepSeek / Ollama / 内嵌引擎三后端 AI 客户端
│   ├── local_engine.py     # llama.cpp 内嵌引擎生命周期管理
│   ├── compiler.py         # 隔离 venv 运行 + 执行行高亮
│   ├── project.py          # .incode 项目文件读写（兼容旧 .ccproj）
│   ├── super_mode.py       # 超能模式管理
│   ├── library_installer.py# 扩展库隔离安装
│   └── exporter.py         # 源码 / exe 导出
├── ui/
│   ├── main_window.py      # 主窗口（双模式切换动画、终端、运行流程）
│   ├── ai_mode.py          # AI 模式（自然语言编辑区）
│   ├── traditional_mode.py # 传统模式（代码编辑器 + AI 面板）
│   ├── widgets/            # 终端、代码编辑器（执行行高亮）、样式
│   ├── dialogs/            # 超能模式六步向导、状态弹窗
│   └── pages/              # 设置页（API / 模型 / 存储 / 超能模式 / 版本）
├── build.py                # 一键构建脚本
└── IN-code.spec            # PyInstaller 配置
```

## 工作原理

```
自然语言描述 ──► AI（翻译器）──► 标准 Python / C / C++ 源码 ──► 隔离环境运行
     │                                                        │
     └──────────── .incode 项目文件（两者同时保存）◄── 逐行执行高亮
```

AI 被严格约束为"翻译器"角色：不补全、不发挥、不生成黑盒框架，
翻译结果必须是可以直接阅读运行的标准源码。

## 许可证

[MIT](LICENSE)
