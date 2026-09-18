# -*- coding: utf-8 -*-
"""
下载真实在线瓦片 —— 对应论文第 2 章的「地图数据下载」。

论文里这一步是用 BIGEMAP / 水经注这类【收费下载器】干的,本文换成直接调
在线瓦片服务的 HTTP 接口。拿到的产物完全一样:标准【谷歌 XYZ】金字塔。

--------------------------------------------------------------
为什么可以直接下?—— 投影
--------------------------------------------------------------
在线地图服务提供的瓦片,本身就是按 Web Mercator(墨卡托)切好的
256x256 图片,编号也遵循 XYZ 规则。所以下下来就是标准原料,
不需要任何投影变换,直接进 convert_tiles.py 转换。

这也是为什么【不能随便找一张世界地图 PNG 来切】:网上大多数世界地图是
等距圆柱投影(经纬度均匀),两者的纬线间距规律不同,混用会导致位置错乱。

--------------------------------------------------------------
瓦片源
--------------------------------------------------------------
  carto —— CartoDB,浅色标准地图,适合当"底图"
  esri  —— Esri 卫星影像,对应论文里的"谷歌影像"

注意两家的 URL 模板【参数顺序不同】:carto 是 {z}/{x}/{y},esri 是 {z}/{y}/{x}。
这是瓦片服务里很常见的一个坑,换源时必须逐个核对。

用法:
    python download_tiles.py                      # 默认 CartoDB,0~5 级
    python download_tiles.py --source esri        # 换卫星影像
    python download_tiles.py --max 6 --clean      # 下到 6 级并先清空
"""

import argparse
import os
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

# 按服务条款要求,必须带上能识别来源的 User-Agent
UA = "MapTileStudy/1.0 (educational use; contact: local)"

SOURCES = {
    "carto": "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "esri": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
}

OUTDIR = "tiles_xyz"


def tile_tasks(min_z, max_z):
    """生成所有要下载的 (z, x, y)。z 级一共有 2^z x 2^z 张。"""
    for z in range(min_z, max_z + 1):
        n = 2 ** z
        for x in range(n):
            for y in range(n):
                yield z, x, y


def fetch_one(template, outdir, z, x, y, retries=3):
    """下载单张瓦片。已存在且非空则跳过,支持断点续传。"""
    path = os.path.join(outdir, str(z), str(x), f"{y}.png")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return "skip"

    url = template.format(z=z, x=x, y=y)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            if not data:
                raise ValueError("空响应")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            return "ok"
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))   # 退避重试,别把服务器打急
    return f"fail:{last_err}"


def dir_size_mb(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total / 1024 / 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="carto", choices=list(SOURCES))
    ap.add_argument("--min", type=int, default=0)
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--out", default=OUTDIR)
    ap.add_argument("--workers", type=int, default=8, help="并发数,别开太大")
    ap.add_argument("--clean", action="store_true", help="先清空输出目录")
    args = ap.parse_args()

    if args.clean and os.path.isdir(args.out):
        shutil.rmtree(args.out)
        print(f"已清空 {args.out}/")

    template = SOURCES[args.source]
    tasks = list(tile_tasks(args.min, args.max))
    print(f"瓦片源: {args.source}")
    print(f"模板: {template}")
    print(f"级别: {args.min} ~ {args.max}   共 {len(tasks)} 张")
    print(f"输出: {args.out}/\n")

    ok = skip = 0
    failures = []
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(fetch_one, template, args.out, z, x, y): (z, x, y)
            for z, x, y in tasks
        }
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            if res == "ok":
                ok += 1
            elif res == "skip":
                skip += 1
            else:
                failures.append((futures[fut], res))

            if i % 200 == 0 or i == len(tasks):
                pct = i / len(tasks) * 100
                print(f"  进度 {i:>5}/{len(tasks)}  ({pct:5.1f}%)  成功 {ok}  跳过 {skip}  失败 {len(failures)}")

    cost = time.time() - t0
    print(f"\n完成: 新下 {ok} 张, 跳过 {skip} 张, 失败 {len(failures)} 张")
    print(f"耗时 {cost:.1f}s   磁盘占用 {dir_size_mb(args.out):.2f} MB")

    if failures:
        print("\n失败的瓦片(前 10 个):")
        for (z, x, y), err in failures[:10]:
            print(f"  {z}/{x}/{y}  {err}")
        print("\n重跑一次本脚本即可续传补下(已存在的会自动跳过)。")


if __name__ == "__main__":
    main()
