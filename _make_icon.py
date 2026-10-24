# -*- coding: utf-8 -*-
"""把生成的图标原图裁切成圆角方块主体并导出多尺寸 .ico"""
from PIL import Image

src = Image.open(r"c:\Users\PC\Desktop\编译器\CreativeCoder\assets\icon_src.jpg").convert("RGB")
w, h = src.size

# 原图 1920x1920，圆角方块主体大约在画面中央 63% 区域（目测比例），
# 直接取中央正方形裁切
side = int(min(w, h) * 0.63)
left = (w - side) // 2
top = int((h - side) / 2) - 10  # 主体略偏上，微调
box = (left, top, left + side, top + side)
icon = src.crop(box)

out = r"c:\Users\PC\Desktop\编译器\CreativeCoder\assets\app.ico"
icon.save(out, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("saved:", out)
