# -*- coding: utf-8 -*-
"""
把源图切成【谷歌 XYZ】金字塔瓦片。

论文第 3.1 节讲的「金字塔瓦片模型」就是这件事:
  - 0 级:整个世界 1 张 256x256
  - 每降一级,画面切成 4 块,瓦片数量变成 4 倍(2x2)
  - 所以 z 级一共有 2^z x 2^z 张瓦片

输出目录结构(谷歌 XYZ 规则):
    tiles_xyz/{z}/{x}/{y}.png
      z = 缩放级别
      x = 列号,从西向东 0 -> 2^z-1
      y = 行号,【从北向南】0 -> 2^z-1      <-- 注意方向,这是后面对比 TMS 的关键

用法:
    python slice_tiles.py              # 切 0~5 级
    python slice_tiles.py --max 7      # 切到 7 级
"""

import argparse
import os
import time

from PIL import Image

SRC = os.path.join("source", "world.png")
OUTDIR = "tiles_xyz"
TILE = 256


def slice_pyramid(img, min_z, max_z, outdir, fmt="png"):
    """把一张完整的墨卡托世界图切成金字塔。返回瓦片总数。"""
    total = 0

    for z in range(min_z, max_z + 1):
        n = 2 ** z                    # 这一级每个方向上的瓦片数
        side = TILE * n               # 这一级整幅图的像素边长

        # 缩放到该级别的整体尺寸。源图本身是完整的墨卡托世界图,
        # 所以「等分成 2^z x 2^z 网格」就是正确的切片方式。
        if side == img.width:
            level_img = img
        else:
            level_img = img.resize((side, side), Image.LANCZOS)

        level_count = 0
        for x in range(n):
            xdir = os.path.join(outdir, str(z), str(x))
            os.makedirs(xdir, exist_ok=True)
            for y in range(n):
                box = (x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE)
                level_img.crop(box).save(os.path.join(xdir, f"{y}.{fmt}"))
                level_count += 1

        total += level_count
        print(f"  z={z:<2}  {n:>3} x {n:<3} = {level_count:>6} 张")

    return total


def dir_size_mb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / 1024 / 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=0, help="最低级别")
    ap.add_argument("--max", type=int, default=5, help="最高级别")
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUTDIR)
    args = ap.parse_args()

    if not os.path.exists(args.src):
        raise SystemExit(f"找不到源图 {args.src}\n先运行: python gen_source.py")

    img = Image.open(args.src).convert("RGB")
    print(f"源图: {args.src}  {img.width}x{img.height}")
    print(f"切级别: {args.min} ~ {args.max}\n")

    t0 = time.time()
    total = slice_pyramid(img, args.min, args.max, args.out)
    cost = time.time() - t0

    print(f"\n完成: {total} 张瓦片, 耗时 {cost:.2f}s")
    print(f"磁盘占用: {dir_size_mb(args.out):.2f} MB")
    print(f"输出目录: {args.out}/")


if __name__ == "__main__":
    main()
