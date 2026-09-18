# -*- coding: utf-8 -*-
"""
瓦片转换算法 —— 复刻论文第 3 章。

论文原文里,这一步是用 VS2010 + Qt + OpenCV 写的一个 GUI 工具干的,
这里用 Python 重写,逻辑完全一致,但能看清每一行在做什么。

论文实现了两类转换:
  3.2.1  瓦片等级转换:把下载到的原始目录结构,重排成目标结构
  3.2.2  存储格式转换:JPG / PNG / Mixed 之间互转

本文复刻的重点是第(1)类里最本质的一件事 —— 【XYZ 与 TMS 的 Y 轴翻转】。

--------------------------------------------------------------------
为什么需要翻转?
--------------------------------------------------------------------
两套编号规则对「行号 Y 从哪头开始数」的约定是相反的:

    谷歌 XYZ :  原点在【左上角】, Y 从上往下数 0 -> 2^z-1
    TMS      :  原点在【左下角】, Y 从下往上数 0 -> 2^z-1

同一张瓦片,在两套规则下的行号满足:

    y_tms = 2^z - 1 - y_xyz

这就是论文公式 (5)(6) 里「转换后行号 C / 列号 R」的实际内容 ——
原文的公式是图片,文本层提取不出来,但结合它对 TMS 的描述,推导唯一。

漏掉这一步的后果:地图能加载、不报错,但是【上下颠倒】。
"""

import argparse
import hashlib
import os
import shutil

from PIL import Image

SRC_DIR = "tiles_xyz"
DST_DIR = "tiles_tms"


def list_levels(root):
    """列出瓦片目录下所有级别(目录名是数字的那些)。"""
    if not os.path.isdir(root):
        return []
    return sorted(int(d) for d in os.listdir(root) if d.isdigit())


def convert_level(src_root, dst_root, z, src_fmt, dst_fmt):
    """
    转换单个级别。返回 (转换张数, 格式改写张数)。

    论文公式 (5)(6) 的落点就在这里:
        y_tms = 2^z - 1 - y_xyz
    """
    n = 2 ** z
    converted = 0
    reformatted = 0

    for x in range(n):
        src_xdir = os.path.join(src_root, str(z), str(x))
        if not os.path.isdir(src_xdir):
            continue

        dst_xdir = os.path.join(dst_root, str(z), str(x))
        os.makedirs(dst_xdir, exist_ok=True)

        for y in range(n):
            src_file = os.path.join(src_xdir, f"{y}.{src_fmt}")
            if not os.path.exists(src_file):
                continue

            # ---- 核心:Y 轴翻转 ----
            y_tms = n - 1 - y
            dst_file = os.path.join(dst_xdir, f"{y_tms}.{dst_fmt}")

            if src_fmt == dst_fmt:
                # 格式相同,直接搬运(论文里说的「瓦片名不变」的情形)
                shutil.copyfile(src_file, dst_file)
            else:
                # 论文 3.2.2 存储格式转换:结合 OpenCV 重新写出图像
                img = Image.open(src_file)
                if dst_fmt == "jpg":
                    # JPG 不支持透明通道,模式不是 RGB 的要先转,RGBA 会直接保存失败
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    img.save(dst_file, quality=85)
                else:
                    img.save(dst_file, format=dst_fmt.upper())
                reformatted += 1

            converted += 1

    return converted, reformatted


def verify_flip(src_root, dst_root, src_fmt, dst_fmt):
    """
    自检:确认翻转真的发生了 —— 用【文件内容哈希】比对,不依赖图像内容。

    z=1 时世界被切成 4 块(2x2),其中:
        XYZ  的 y=0 是北半球,y=1 是南半球
        TMS  的 y=0 是南半球,y=1 是北半球

    所以转换后应当满足【交叉相等】:

        tiles_tms/1/0/0  ==  tiles_xyz/1/0/1     (南半球那块,行号被换了)
        tiles_tms/1/0/1  ==  tiles_xyz/1/0/0     (北半球那块,行号被换了)

    只要两条都成立,翻转就是对的。这个判据对任何图像都成立 ——
    不管源图是画出来的网格,还是从在线服务下载的真地图。
    """
    def md5(path):
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    ok = True
    for y_tms, y_xyz in (("0", "1"), ("1", "0")):
        p_tms = os.path.join(dst_root, "1", "0", f"{y_tms}.{dst_fmt}")
        p_xyz = os.path.join(src_root, "1", "0", f"{y_xyz}.{src_fmt}")
        if not (os.path.exists(p_tms) and os.path.exists(p_xyz)):
            return None

        same = md5(p_tms) == md5(p_xyz)
        ok = ok and same
        side = "南" if y_tms == "0" else "北"
        mark = "一致" if same else "不一致"
        print(f"    TMS 1/0/{y_tms} ({side}半球)  ==  XYZ 1/0/{y_xyz}   ->  {mark}")

    return ok


def dir_size_mb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / 1024 / 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC_DIR)
    ap.add_argument("--dst", default=DST_DIR)
    ap.add_argument("--src-fmt", default="png")
    ap.add_argument("--dst-fmt", default="png", choices=["png", "jpg"],
                    help="论文 3.2.2 的存储格式转换")
    ap.add_argument("--clean", action="store_true", help="先清空输出目录")
    args = ap.parse_args()

    if args.clean and os.path.isdir(args.dst):
        shutil.rmtree(args.dst)

    levels = list_levels(args.src)
    if not levels:
        raise SystemExit(f"{args.src} 下没有找到级别目录,先运行 slice_tiles.py")

    print(f"源: {args.src}/   格式 {args.src_fmt}")
    print(f"目标: {args.dst}/  格式 {args.dst_fmt}")
    print(f"级别: {levels}\n")

    grand_total = 0
    grand_reformat = 0
    for z in levels:
        n = 2 ** z
        count, refmt = convert_level(args.src, args.dst, z, args.src_fmt, args.dst_fmt)
        expect = n * n
        flag = "OK" if count == expect else "!!"
        print(f"  z={z:<2} {count:>6}/{expect:<6} 张  Y翻转  y -> {n - 1} - y   [{flag}]")
        grand_total += count
        grand_reformat += refmt

    print(f"\n共转换 {grand_total} 张", end="")
    if grand_reformat:
        print(f",其中格式重写 {grand_reformat} 张", end="")
    print(f"\n磁盘占用: {dir_size_mb(args.dst):.2f} MB")

    print("\n翻转自检(哈希比对:转换前后的瓦片内容应当交叉相等):")
    ok = verify_flip(args.src, args.dst, args.src_fmt, args.dst_fmt)
    if ok is True:
        print("  -> 通过:行号确实翻转了,内容一一对应")
    elif ok is False:
        print("  -> 失败:地图会上下颠倒,检查 y_tms = 2^z - 1 - y 这行")
    else:
        print("  -> 跳过:找不到 z=1 的瓦片,无法自检")


if __name__ == "__main__":
    main()
