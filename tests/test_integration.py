# -*- coding: utf-8 -*-
"""
L1 集成测试 —— 校验磁盘上的产物契约。

这一层是本项目的重点:

  * 项目自带的 verify_flip() 只验 z=1 的两张瓦片(见 convert_tiles.py)。
    这里把同样的判据【扩展到全量 1365 张】—— 这就是一次覆盖度提升,
    也是测试岗最想看到的那种「把已有自检做成真正可回归的断言」。

  * 同时补齐负向用例:源瓦片缺失、产物残缺时,脚本必须把问题暴露出来,
    而不是安静地跑完。
"""

import os
import subprocess
import sys

import allure
import pytest

import convert_tiles as ct
from conftest import PROJECT_ROOT, TILE_COUNT, TMS_DIR, XYZ_DIR, md5_file


def _run(script, *args):
    """在项目根目录下跑一个脚本,返回 CompletedProcess。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, script, *args],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )


# ---------------------------------------------------------------- 正向:产物契约

@pytest.mark.parametrize("root,label", [(XYZ_DIR, "tiles_xyz"), (TMS_DIR, "tiles_tms")])
@allure.feature("L1 集成测试")
@allure.story("产物数量契约")
@allure.title("每级瓦片数等于 4^z（{label}）")
def test_i01_tile_count_per_level(root, label):
    """I-01 每级瓦片数必须等于 4^z,z0~z5 合计 1365 张。"""
    levels = ct.list_levels(str(root))
    assert levels, f"{label} 下没有级别目录"
    assert levels == [0, 1, 2, 3, 4, 5], f"{label} 级别不连续: {levels}"

    total = 0
    for z in levels:
        n = 2 ** z
        actual = 0
        for x in range(n):
            xdir = root / str(z) / str(x)
            if xdir.is_dir():
                actual += len([f for f in os.listdir(xdir) if f.endswith(".png")])
        assert actual == n * n, f"{label} z={z} 应有 {n*n} 张,实际 {actual}"
        total += actual
    assert total == TILE_COUNT, f"{label} 合计 {total} 张,期望 {TILE_COUNT}"


@pytest.mark.parametrize("root,label", [(XYZ_DIR, "tiles_xyz"), (TMS_DIR, "tiles_tms")])
@allure.feature("L1 集成测试")
@allure.story("命名契约")
@allure.title("文件名与行列号契约（{label}）")
def test_i02_naming_contract(root, label):
    """I-02 文件名必须严格匹配 {z}/{x}/{y}.png,且 x/y 落在 [0, 2^z-1]。

    目录结构就是瓦片服务的对外接口,命名错一位就是 404。
    """
    bad = []
    for z in ct.list_levels(str(root)):
        n = 2 ** z
        for x in range(n):
            xdir = root / str(z) / str(x)
            if not xdir.is_dir():
                bad.append(f"缺列目录 {z}/{x}")
                continue
            for name in os.listdir(xdir):
                if not name.endswith(".png"):
                    bad.append(f"非 png 文件 {z}/{x}/{name}")
                    continue
                stem = name[:-4]
                if not stem.isdigit():
                    bad.append(f"行号非数字 {z}/{x}/{name}")
                    continue
                if not 0 <= int(stem) <= n - 1:
                    bad.append(f"行号越界 {z}/{x}/{name}")
    assert not bad, f"{label} 命名契约违例 {len(bad)} 处: {bad[:10]}"


@allure.feature("L1 集成测试")
@allure.story("翻转一致性")
@allure.title("全量 1365 张 XYZ/TMS 交叉比对")
def test_i03_full_cross_content_match():
    """I-03(核心) 全量交叉比对:

        TMS  z/x/y   的内容  ==  XYZ  z/x/(2^z - 1 - y)  的内容

    项目自带的 verify_flip() 只抽查 z=1 的两张。这里把 1365 张全部查一遍 ——
    只要有一条不成立,地图就会上下颠倒,而这恰恰是肉眼最不容易当场发现的 bug。
    """
    levels = ct.list_levels(str(XYZ_DIR))
    assert levels, "tiles_xyz 下没有级别目录,先跑 slice_tiles.py 或 download_tiles.py"

    checked, mismatches, missing = 0, [], []
    for z in levels:
        n = 2 ** z
        for x in range(n):
            for y in range(n):
                p_xyz = XYZ_DIR / str(z) / str(x) / f"{y}.png"
                p_tms = TMS_DIR / str(z) / str(x) / f"{n - 1 - y}.png"
                if not (p_xyz.exists() and p_tms.exists()):
                    missing.append((z, x, y))
                    continue
                if md5_file(p_xyz) != md5_file(p_tms):
                    mismatches.append({"xyz": f"{z}/{x}/{y}", "tms": f"{z}/{x}/{n-1-y}"})
                checked += 1

    assert not missing, f"缺失瓦片 {len(missing)} 张: {missing[:10]}"
    assert not mismatches, (f"翻转内容不一致 {len(mismatches)} 处(地图会颠倒): "
                            f"{mismatches[:10]}")
    assert checked == TILE_COUNT, f"只比对了 {checked} 张,期望 {TILE_COUNT}"


@allure.feature("L1 集成测试")
@allure.story("翻转一致性")
@allure.title("仅 Y 轴翻转，列号原样保留")
def test_i04_only_y_axis_flips():
    """I-04 只有行号(y)翻转,列号(x)必须原样保留。

    防的是「整体反转 / 行列都翻」这类假成功 —— 那种情况下 z=1 的自检
    有可能歪打正着地通过,但更高级别全错。
    """
    for z in ct.list_levels(str(XYZ_DIR)):
        n = 2 ** z
        expect = {str(i) for i in range(n)}
        cols_xyz = {d for d in os.listdir(XYZ_DIR / str(z)) if d.isdigit()}
        cols_tms = {d for d in os.listdir(TMS_DIR / str(z)) if d.isdigit()}
        assert cols_xyz == expect, f"z={z} tiles_xyz 列号不符: {sorted(cols_xyz)}"
        assert cols_tms == expect, f"z={z} tiles_tms 列号不符: {sorted(cols_tms)}"


@allure.feature("L1 集成测试")
@allure.story("文档一致性")
@allure.title("README 声称的 1365 张与实际一致")
def test_i10_artifact_count_matches_readme():
    """I-10 文档一致性:README 1.3.2 声称 1365 张,实际产物必须吻合。"""
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "1365" in readme, "README 里的瓦片总数说明被改动了,需同步本用例"

    actual = sum(
        len([f for f in files if f.endswith(".png")])
        for _, _, files in os.walk(TMS_DIR)
    )
    assert actual == 1365, f"实际 {actual} 张,与文档声称的 1365 张不符"


# ---------------------------------------------------------------- 负向 / 边界

@allure.feature("L1 集成测试")
@allure.story("负向用例")
@allure.title("源瓦片缺失时如实报告数量")
def test_i07_missing_source_tile_is_reported(tmp_path):
    """I-07(负向) 源瓦片缺失时计数必须小于期望值 —— 问题要能被暴露。

    z=1 理论上应有 2x2=4 张,这里只放 3 张(故意缺 1/1/1),
    断言 count 如实返回 3,而不是悄悄按 4 记账。

    注意:convert_level 是按 0..n-1 的编号【查找】文件,并不扫描目录,
    所以多放进来的编号外文件对它不可见 —— 第一版用例就栽在这个假设上。
    """
    src, dst = tmp_path / "tiles_xyz", tmp_path / "tiles_tms"
    for x in range(2):
        (src / "1" / str(x)).mkdir(parents=True)
    for x, y in ((0, 0), (0, 1), (1, 0)):      # 缺 (1, 1)
        (src / "1" / str(x) / f"{y}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    expect = 2 ** 1 * 2 ** 1
    count, _ = ct.convert_level(str(src), str(dst), 1, "png", "png")
    assert count == 3, f"应如实返回 3(缺 1 张),实际 {count}"
    assert count < expect, "计数等于期望值,缺失被掩盖了"


@allure.feature("L1 集成测试")
@allure.story("格式转换")
@allure.title("JPG 转换产物可解码且尺寸不变")
def test_i08_jpg_conversion_outputs_valid_images(tmp_path):
    """I-08 格式转换(论文 3.2.2):产物必须可解码、尺寸不变、无 0 字节文件。"""
    from PIL import Image

    src, dst = tmp_path / "s", tmp_path / "d"
    (src / "1" / "0").mkdir(parents=True)
    for y in range(2):
        Image.new("RGB", (256, 256), (y * 100, 50, 200)).save(src / "1" / "0" / f"{y}.png")

    count, reformatted = ct.convert_level(str(src), str(dst), 1, "png", "jpg")
    assert count == 2 and reformatted == 2

    for y in range(2):
        out = dst / "1" / "0" / f"{y}.jpg"
        assert out.exists() and out.stat().st_size > 0, "产出了空文件"
        with Image.open(out) as im:
            assert im.format == "JPEG"
            assert im.size == (256, 256), "格式转换不应改变尺寸"


@allure.feature("L1 集成测试")
@allure.story("格式转换")
@allure.title("RGBA 转 JPG 不崩溃且剥离透明通道")
def test_i09_rgba_tile_converts_to_jpg_without_crash(tmp_path):
    """I-09 带透明通道的源图转 JPG 不能抛异常。

    JPG 没有 alpha 通道,RGBA 直接 save 会失败 —— 这是 README 里记的坑,
    代码里有对应的 convert("RGB") 分支,这里钉住它。
    """
    from PIL import Image

    src, dst = tmp_path / "s", tmp_path / "d"
    (src / "0" / "0").mkdir(parents=True)
    Image.new("RGBA", (256, 256), (255, 0, 0, 128)).save(src / "0" / "0" / "0.png")

    count, _ = ct.convert_level(str(src), str(dst), 0, "png", "jpg")
    assert count == 1
    with Image.open(dst / "0" / "0" / "0.jpg") as im:
        assert im.mode == "RGB", "透明通道没有被正确剥离"


@pytest.mark.slow
@allure.feature("L1 集成测试")
@allure.story("脚本行为")
@allure.title("--clean 清空陈旧产物")
def test_i06_clean_purges_stale_output(tmp_path):
    """I-06 --clean 必须清空输出目录,不留上次运行的残渣。"""
    src, dst = tmp_path / "tiles_xyz", tmp_path / "tiles_tms"
    (src / "1" / "0").mkdir(parents=True)
    for y in range(2):
        (src / "1" / "0" / f"{y}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (dst / "stale").mkdir(parents=True)
    (dst / "stale" / "leftover.txt").write_text("上一次的旧产物", encoding="utf-8")

    result = _run("convert_tiles.py", "--src", str(src), "--dst", str(dst), "--clean")
    assert result.returncode == 0, result.stderr
    assert not (dst / "stale").exists(), "--clean 没有清除旧目录"


@pytest.mark.slow
@allure.feature("L1 集成测试")
@allure.story("脚本行为")
@allure.title("重复转换产物完全一致（幂等）")
def test_i05_conversion_is_idempotent(tmp_path):
    """I-05 幂等性:重复转换必须得到完全一致的产物(MD5 层面)。"""
    out = tmp_path / "tiles_tms"
    result = _run("convert_tiles.py", "--dst", str(out))
    assert result.returncode == 0, result.stderr

    diff = []
    for z in ct.list_levels(str(TMS_DIR)):
        n = 2 ** z
        for x in range(n):
            for y in range(n):
                a = TMS_DIR / str(z) / str(x) / f"{y}.png"
                b = out / str(z) / str(x) / f"{y}.png"
                if not b.exists() or md5_file(a) != md5_file(b):
                    diff.append(f"{z}/{x}/{y}")
    assert not diff, f"复算产物与现有产物不一致 {len(diff)} 处: {diff[:10]}"


# 缺陷回归用例见 tests/test_defects.py(D-01 断点续传判据、D-06 文档不一致)
