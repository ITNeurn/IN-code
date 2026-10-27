# IN-code

**用自然语言，写出真代码。**

IN-code 是一款 Windows 桌面编程学习软件（Python + PyQt6 + C）。核心理念是
**"AI 只当翻译器"**：你用自然语言写下逻辑流程，AI 把它翻译成 Python / C / C++ / Java / H5
标准源码，而不是生成一个看不懂的黑盒。所有生成的代码都可以打开逐行查看、
编辑、运行，帮助你真正理解每一行代码。

![平台](https://img.shields.io/badge/Windows-10%2B-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-green) ![License](https://img.shields.io/badge/License-MIT-orange)

## 特性

- **五种编程语言**：Python / C / C++ / Java / H5，编辑器语法高亮，一键编译运行
  （H5 直接在浏览器中打开预览；Java 需本机 JDK）
- **在线增量更新**：设置页一键检查更新，只下载几 MB 的主程序增量包
  （4 线程分块下载、逐块重试、sha256 强校验、失败自动回滚），
  不必每次重下 4.4 GB 完整安装包
- **双模式界面**
  - **AI 模式**：一个大编辑区，只写自然语言；AI 翻译后的代码在后台保留，
    一键运行。模式切换带平滑过渡动画。
  - **传统模式**：完整的代码编辑器 + 终端输出，运行时逐行高亮当前执行行。
- **云端 + 本地双 AI 后端**
  - 云端：DeepSeek API（OpenAI 兼容接口，可自定义地址）
  - 本地：内嵌 llama.cpp 引擎 + 打包内置的 DeepSeek R1 7B GGUF 模型，
    离线也能用；或连接本机 Ollama
- **严格输出协议**：AI 只输出代码本身；听不懂时输出 `{INX}print：（原因）{INY}`
  并弹出澄清页，而不是瞎编代码；需要第三方库时输出 `{UNX}text：（库名）{UNY}`，
  软件自动安装后重新翻译
- **隔离运行环境**：所有代码在用户目录下的独立 venv 中运行，不污染系统
- **超能模式**：六步向导解锁离线能力包——128 个 Python 第三方库分批
  多线程并行下载（6 路，先批量下 wheel 再本地离线安装），可选追加
  MoE 大模型；进度实时可见，支持转到后台运行
- **自定义项目文件** `.incode`：自然语言描述与生成代码同时保存，纯文本可读
- **导出**：一键导出标准源码、打包成独立 exe，或通过 WSL2 自动构建 Android APK
  （首次使用会引导安装 WSL2，构建在后台运行、日志实时显示）

## 下载安装

**永久下载地址**（始终指向最新版本，不会随版本号变化）：

| 分卷 | 下载链接 |
| --- | --- |
| 第 1 卷 | https://github.com/ITNeurn/IN-code/releases/latest/download/IN-code.7z.001 |
| 第 2 卷 | https://github.com/ITNeurn/IN-code/releases/latest/download/IN-code.7z.002 |
| 第 3 卷 | https://github.com/ITNeurn/IN-code/releases/latest/download/IN-code.7z.003 |
| 第 4 卷 | https://github.com/ITNeurn/IN-code/releases/latest/download/IN-code.7z.004 |

下载全部 4 个分卷后，用 7-Zip 解压 `IN-code.7z.001` 即得到 `IN-code-2.0-sfx.exe` 自解压安装包，运行即安装（内含 DeepSeek R1 7B 模型）。

> 安装包约 4.4 GB（内置 4.7 GB 本地模型），解压后约需 5 GB 磁盘空间。
> 已安装旧版本的用户无需重下完整安装包：软件内 **设置 → 版本信息 → 检查更新**
> 即可增量在线更新（多线程分块下载 + sha256 校验，失败自动回滚）。

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
自然语言描述 ──► AI（翻译器）──► 标准 Python / C / C++ / Java / H5 源码 ──► 隔离环境运行
     │                                                        │
     └──────────── .incode 项目文件（两者同时保存）◄── 逐行执行高亮
```

AI 被严格约束为"翻译器"角色：不补全、不发挥、不生成黑盒框架，
翻译结果必须是可以直接阅读运行的标准源码。

## 许可证

[MIT](LICENSE)
