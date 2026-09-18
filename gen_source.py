# -*- coding: utf-8 -*-
"""
生成一张 Web Mercator 投影的「世界图」,作为瓦片源图。

用途:替代论文中用 BIGEMAP / 水经注下载的谷歌影像数据。
论文的源数据是收费下载器抓来的,这里自己画一张 —— 内容不重要,
重要的是它必须是【正确的墨卡托投影】,并且带上可用于核对的参照物:

  1. 经纬网格    —— 切片后在 Leaflet 里网格线要对得上
  2. 地标点      —— 已知经纬度的城市,加载后位置必须吻合
  3. 上下色带    —— 顶部红、底部蓝,用来验证 TMS 的 Y 轴翻转
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 4096                 # 源图边长(像素)
LAT_LIMIT = 85.05112878     # Web Mercator 的纬度截断(超过这个值投影会发散)
OUT = os.path.join("source", "world.png")

# 画图用的颜色
OCEAN = (16, 42, 67)
GRID = (58, 96, 130)
EQUATOR = (90, 150, 200)
LANDMARK = (255, 196, 0)
TEXT = (235, 240, 245)
BAND_TOP = (200, 40, 40)
BAND_BOTTOM = (40, 90, 200)

# 经纬度 -> 像素。经度是线性映射,纬度要走墨卡托公式(这就是它和等距圆柱投影的区别)
def lon_to_px(lon, size=SIZE):
    return (lon + 180.0) / 360.0 * size


def lat_to_px(lat, size=SIZE):
    lat = max(-LAT_LIMIT, min(LAT_LIMIT, lat))
    r = math.radians(lat)
    y = (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0
    return y * size


def load_font(px):
    """找一个能显示中文的字体,找不到就退回 PIL 默认位图字体。"""
    for name in ("msyh.ttc", "simhei.ttf", "simsun.ttc"):
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            return ImageFont.truetype(path, px)
    return ImageFont.load_default()


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img = Image.new("RGB", (SIZE, SIZE), OCEAN)
    d = ImageDraw.Draw(img, "RGBA")
    font = load_font(28)
    small = load_font(20)

    # ---- 1. 经纬网格 ----
    # 经线:每 30 度一条。墨卡托投影下经线是等距的竖线。
    for lon in range(-180, 181, 30):
        x = lon_to_px(lon)
        d.line([(x, 0), (x, SIZE)], fill=GRID, width=2)
        if lon != -180:
            d.text((x + 6, SIZE / 2 + 8), f"{lon}E" if lon > 0 else f"{lon}", font=small, fill=TEXT)

    # 纬线:每 30 度一条,间距是【不均匀】的 —— 越靠近两极被拉得越开。
    # 这正是墨卡托投影的特征,切片后网格线的疏密能直接反映投影对不对。
    for lat in range(-60, 61, 30):
        y = lat_to_px(lat)
        d.line([(0, y), (SIZE, y)], fill=GRID, width=2)
        d.text((10, y + 6), f"{lat}N" if lat > 0 else (f"{lat}S" if lat < 0 else "0"), font=small, fill=TEXT)

    # 赤道加粗,作为最直观的居中参照
    y0 = lat_to_px(0)
    d.line([(0, y0), (SIZE, y0)], fill=EQUATOR, width=4)

    # ---- 2. 上下色带 ----
    # 用来看 TMS 翻转:如果加载出来红色在下面,说明 Y 轴搞反了。
    band = int(SIZE * 0.015)
    d.rectangle([0, 0, SIZE, band], fill=BAND_TOP)
    d.rectangle([0, SIZE - band, SIZE, SIZE], fill=BAND_BOTTOM)
    d.text((SIZE / 2 - 60, band + 6), "TOP", font=font, fill=BAND_TOP)
    d.text((SIZE / 2 - 90, SIZE - band - 40), "BOTTOM", font=font, fill=BAND_BOTTOM)

    # ---- 3. 地标点 ----
    # 已知经纬度的城市。切片后位置若吻合,说明整条投影链路是正确的。
    landmarks = [
        ("Beijing", 116.40, 39.90),
        ("Shanghai", 121.47, 31.23),
        ("Guangzhou", 113.26, 23.13),
        ("Urumqi", 87.62, 43.83),
        ("Lhasa", 91.11, 29.65),
        ("Nanchang", 115.86, 28.68),   # 论文作者所在城市
        ("London", -0.13, 51.51),
        ("NewYork", -74.01, 40.71),
        ("Sydney", 151.21, -33.87),
    ]
    for name, lon, lat in landmarks:
        x, y = lon_to_px(lon), lat_to_px(lat)
        r = 10
        d.ellipse([x - r, y - r, x + r, y + r], fill=LANDMARK)
        d.text((x + r + 6, y - 12), name, font=small, fill=TEXT)

    img.save(OUT)
    print(f"源图已生成: {OUT}  ({SIZE}x{SIZE})")
    print(f"覆盖范围: 经度 -180~180, 纬度 ±{LAT_LIMIT}")


if __name__ == "__main__":
    main()
