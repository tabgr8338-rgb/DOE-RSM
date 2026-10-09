"""アプリのアイコン（DOE-RSM.ico）を作る。ビルド時に実行する。"""
import sys

from PIL import Image, ImageDraw, ImageFont

out = sys.argv[1]
size = 256
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([8, 8, size - 8, size - 8], radius=48, fill=(31, 78, 121, 255))
# 応答曲面の等高線を思わせる楕円
for i, r in enumerate((92, 66, 40)):
    c = (255, 255, 255, 90 + 55 * i)
    d.ellipse([128 - r, 150 - int(r * 0.62), 128 + r, 150 + int(r * 0.62)], outline=c, width=7)
d.ellipse([118, 140, 138, 160], fill=(255, 196, 0, 255))
font = ImageFont.load_default(size=64)
d.text((128, 62), "DOE", font=font, fill="white", anchor="mm")
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
