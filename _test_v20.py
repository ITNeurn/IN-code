# -*- coding: utf-8 -*-
"""v2.0 新功能测试：在线更新器 + Java/H5 语言支持。"""
import json
import os
import sys
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print("PASS", name)
    else:
        failed += 1
        print("FAIL", name)


# ================================================================ 更新器
from core import updater
from config.settings import APP_VERSION

# 版本比较
check("版本解析 v1.2", updater.parse_version("v1.2") == (1, 2))
check("版本解析 2.0.1", updater.parse_version("2.0.1") == (2, 0, 1))
check("版本比较 1.2<2.0", updater.parse_version("v1.2") < updater.parse_version("2.0"))
check("版本比较 2.0==2.0", updater.parse_version("v2.0") == updater.parse_version("2.0"))

# 更新包资产查找
assets = [{"name": "update-2.0.zip", "size": 1, "url": "u"},
          {"name": "IN-code.7z.001", "size": 1, "url": "u"}]
check("找到更新包", updater.find_update_asset(assets, "2.0") is not None)
check("版本不匹配时找不到", updater.find_update_asset(assets, "9.9") is None)

# 更新包构建+校验闭环
tmp = Path(os.environ["TEMP"]) / "incode_upd_test"
import shutil
shutil.rmtree(tmp, ignore_errors=True)
dist = tmp / "IN-code"
(dist / "_internal" / "assets").mkdir(parents=True)
(dist / "IN-code.exe").write_bytes(b"fake exe v2")
(dist / "_internal" / "assets" / "app.ico").write_bytes(b"fake icon")
(dist / "models").mkdir()  # 模型目录不应进更新包
(dist / "models" / "big.gguf").write_bytes(b"x" * 100)

pkg = tmp / "update-2.0.zip"
updater.build_update_package(dist, pkg, "2.0")
with zipfile.ZipFile(pkg) as z:
    names = z.namelist()
check("更新包含exe", "IN-code.exe" in names)
check("更新包含assets", "_internal/assets/app.ico" in names)
check("更新包含manifest", "manifest.json" in names)
check("更新包排除模型", not any("models/" in n for n in names))

files = updater.verify_package(pkg, tmp / "extract")
check("校验通过返回2个文件", len(files) == 2)

# 篡改检测
bad = tmp / "bad.zip"
shutil.copy2(pkg, bad)
# 直接改包内 exe 字节再封一个坏包
with zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("IN-code.exe", b"tampered")
    with zipfile.ZipFile(pkg) as z0:
        manifest = z0.read("manifest.json").decode("utf-8")
        z.writestr("_internal/assets/app.ico", z0.read("_internal/assets/app.ico"))
    z.writestr("manifest.json", manifest)
try:
    updater.verify_package(bad, tmp / "extract2")
    check("篡改被检出", False)
except IOError:
    check("篡改被检出", True)

# ================================================================ 语言支持
from core.project import LANG_EXT, LANG_NAMES
check("LANG_EXT含java", LANG_EXT["java"] == ".java")
check("LANG_EXT含h5", LANG_EXT["h5"] == ".html")
check("LANG_NAMES含Java", LANG_NAMES["java"] == "Java")
check("LANG_NAMES含H5", LANG_NAMES["h5"] == "H5")

from core.ai_client import system_prompt, parse_ai_reply
p_java = system_prompt("java")
check("Java提示词要求Main类", "public class Main" in p_java and "main(String[] args)" in p_java)
p_h5 = system_prompt("h5")
check("H5提示词要求完整HTML", "<!DOCTYPE html>" in p_h5 and "内联" in p_h5)
check("H5提示词禁止外链", "不引用任何外部文件" in p_h5)
p_py = system_prompt("python")
check("Python提示词无附加规则", "public class Main" not in p_py)

# 解析 Java/H5 代码块
r = parse_ai_reply("```java\npublic class Main {}\n```", "java")
check("Java代码块剥离", r.ok and "public class Main" in r.code and "```" not in r.code)
r = parse_ai_reply("```html\n<!DOCTYPE html><html></html>\n```", "h5")
check("H5代码块剥离", r.ok and r.code.startswith("<!DOCTYPE html>"))

# 编辑器关键字
from ui.widgets.code_editor import SimpleHighlighter
check("Java关键字集", "public" in SimpleHighlighter.KEYWORDS["java"])
check("H5关键字集", "function" in SimpleHighlighter.KEYWORDS["h5"] and "script" in SimpleHighlighter.KEYWORDS["h5"])

# 运行器分支
from core import compiler
w = compiler.RunWorker("public class Main {}", "java")
check("Java运行分支存在", hasattr(w, "_run_java"))
w2 = compiler.RunWorker("<!DOCTYPE html>", "h5")
check("H5运行分支存在", hasattr(w2, "_run_h5"))

# H5 运行：mock webbrowser，不落真实浏览器
import webbrowser
opened = []
orig_open = webbrowser.open
webbrowser.open = lambda url: opened.append(url) or True
events = []
w2.output.connect(lambda s: events.append(("out", s)))
w2.done.connect(lambda c: events.append(("done", c)))
w2.run()
webbrowser.open = orig_open
idx = compiler.SRC_DIR / "index.html"
check("H5写出index.html", idx.exists() and idx.read_text(encoding="utf-8").startswith("<!DOCTYPE html>"))
check("H5浏览器已调起", len(opened) == 1 and opened[0].startswith("file:///"))
check("H5运行正常结束", ("done", 0) in events)

# Java 无 JDK 时的失败提示（mock find_java 返回空）
orig_fj = compiler.find_java
compiler.find_java = lambda: (None, None)
fails = []
w3 = compiler.RunWorker("x", "java")
w3.failed.connect(lambda s: fails.append(s))
w3.run()
check("无JDK给出明确提示", fails and "JDK" in fails[0])
compiler.find_java = orig_fj

# env_status 新增 java 项
st = compiler.environment_status()
check("环境状态含javac", "javac" in st and "java" in st)

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n通过 {passed}，失败 {failed}")
sys.exit(1 if failed else 0)
