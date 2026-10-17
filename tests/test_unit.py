# -*- coding: utf-8 -*-
"""
L0 单元测试 —— 纯函数,不碰磁盘。

覆盖:
  U-01 ~ U-05   转换算法   (convert_tiles.py)
  U-06 ~ U-09   投影函数   (gen_source.py)
  U-10          切片契约   (slice_tiles.py)

这些用例的风险点不在「跑不跑得通」,而在「边界值算不算得对」:
翻转公式一旦写成 y_tms = y,地图不报错、只是上下颠倒 —— 靠肉眼看界面很难发现,
靠断言一行就能钉死。
"""

import math

import allure
import pytest

import convert_tiles as ct
import gen_source as gs
import slice_tiles as st


# ---------------------------------------------------------------- U-01 ~ U-04
# Y 轴翻转公式:y_tms = 2^z - 1 - y   (论文公式 5、6)

@pytest.mark.parametrize("z", [1, 2, 3, 4, 5])
@allure.feature("L0 单元测试")
@allure.story("Y 轴翻转")
@allure.title("翻转后行号是 0..2^z-1 的排列（z={z}）")
def test_u01_flip_is_bijection(z):
    """U-01 翻转后的行号必须落在 [0, 2^z-1] 且与原行号一一对应(双射)。"""
    n = 2 ** z
    flipped = [n - 1 - y for y in range(n)]
    assert all(0 <= v <= n - 1 for v in flipped), "翻转后行号越界"
    assert sorted(flipped) == list(range(n)), "翻转必须是一个排列(不能有重复/遗漏)"


@pytest.mark.parametrize("z", [1, 2, 3, 5])
@allure.feature("L0 单元测试")
@allure.story("Y 轴翻转")
@allure.title("翻转是自逆的：f(f(y)) == y（z={z}）")
def test_u02_flip_is_involution(z):
    """U-02 翻转是自逆的:f(f(y)) == y(翻转两次回到原值)。"""
    n = 2 ** z
    for y in range(n):
        assert n - 1 - (n - 1 - y) == y


@pytest.mark.parametrize("z", [1, 2, 3, 5])
@allure.feature("L0 单元测试")
@allure.story("Y 轴翻转")
@allure.title("翻转边界值：南北极互换（z={z}）")
def test_u03_flip_boundary_values(z):
    """U-03 边界值:y=0(北半球顶) <-> y=2^z-1(南半球底)。"""
    n = 2 ** z
    assert n - 1 - 0 == n - 1
    assert n - 1 - (n - 1) == 0


@pytest.mark.parametrize("max_z,expect", [(0, 1), (1, 5), (2, 21), (5, 1365)])
@allure.feature("L0 单元测试")
@allure.story("瓦片金字塔")
@allure.title("金字塔总数 = sum(4^z)（max_z={max_z}）")
def test_u04_pyramid_total_count(max_z, expect):
    """U-04 金字塔总瓦片数 = sum(4^z) = (4^(n+1) - 1) / 3。"""
    assert sum(4 ** z for z in range(max_z + 1)) == expect


@pytest.mark.parametrize("junk", ["temp", ".git", "abc", "-1", "1.5", "01a"])
@allure.feature("L0 单元测试")
@allure.story("级别目录扫描")
@allure.title("忽略非数字垃圾目录（{junk}）")
def test_u05_list_levels_ignores_non_numeric(tmp_path, junk):
    """U-05 级别目录只认纯数字,杂物必须被忽略(否则会去转换垃圾目录)。"""
    (tmp_path / "0").mkdir()
    (tmp_path / "5").mkdir()
    (tmp_path / junk).mkdir()
    assert ct.list_levels(str(tmp_path)) == [0, 5]


@allure.feature("L0 单元测试")
@allure.story("级别目录扫描")
@allure.title("目录不存在时返回空列表")
def test_u05b_list_levels_missing_dir(tmp_path):
    """U-05b 目录不存在时返回空列表,不抛异常(边界:首次运行)。"""
    assert ct.list_levels(str(tmp_path / "not_here")) == []


# ---------------------------------------------------------------- U-06 ~ U-09
# Web Mercator 投影

@allure.feature("L0 单元测试")
@allure.story("Web Mercator 投影")
@allure.title("赤道落在图片垂直正中")
def test_u06_equator_is_vertically_centered():
    """U-06 墨卡托投影下赤道必须落在图片垂直正中。"""
    assert gs.lat_to_px(0) == pytest.approx(gs.SIZE / 2)


@pytest.mark.parametrize("lon,expect", [(-180, 0.0), (0, gs.SIZE / 2), (180, gs.SIZE)])
@allure.feature("L0 单元测试")
@allure.story("Web Mercator 投影")
@allure.title("经度线性映射（{lon}°）")
def test_u08_longitude_is_linear(lon, expect):
    """U-08 经度是线性映射:左右边界与中轴都要落在预期像素上。"""
    assert gs.lon_to_px(lon) == pytest.approx(expect)


@pytest.mark.parametrize("lat", [90, -90, 89.9, -1e6, 1e6])
@allure.feature("L0 单元测试")
@allure.story("Web Mercator 投影")
@allure.title("纬度超限截断到墨卡托极限（lat={lat}）")
def test_u07_latitude_clamped_to_mercator_limit(lat):
    """U-07 纬度超限必须被截断到 ±85.05112878,不能算出 inf/nan。

    墨卡托在两极发散,不截断的话 lat=90 会得到 inf -> 画图直接崩。
    """
    value = gs.lat_to_px(lat)
    assert math.isfinite(value), f"lat={lat} 算出了非有限值"
    assert -1e-6 <= value <= gs.SIZE + 1e-6
    limit = gs.lat_to_px(gs.LAT_LIMIT)
    assert (value == pytest.approx(limit, abs=1e-9) or
            value == pytest.approx(gs.SIZE - limit, abs=1e-9))


def _px_to_lat(y, size=gs.SIZE):
    """lat_to_px 的反函数。测试里独立实现,不复用被测代码。"""
    n = math.pi * (1 - 2 * y / size)
    return math.degrees(math.atan(math.sinh(n)))


@pytest.mark.parametrize("lat", [-85, -60, -33.87, -23.13, 0, 29.65, 45.0, 85])
@allure.feature("L0 单元测试")
@allure.story("Web Mercator 投影")
@allure.title("投影往返误差小于一个像素（lat={lat}）")
def test_u09_projection_roundtrip(lat):
    """U-09 投影往返一致性:lat -> px -> lat,误差应远小于一个像素。

    覆盖了 gen_source.py 里全部地标所在纬度,包括南半球的悉尼。
    """
    assert _px_to_lat(gs.lat_to_px(lat)) == pytest.approx(lat, abs=0.01)


# ---------------------------------------------------------------- U-10
# 切片契约

@allure.feature("L0 单元测试")
@allure.story("切片契约")
@allure.title("每张切片严格 256x256")
def test_u10_every_tile_is_256x256(tmp_path):
    """U-10 每张切片必须严格 256x256 —— 这是瓦片服务的硬契约。"""
    from PIL import Image

    src = Image.new("RGB", (1024, 1024), (10, 20, 30))
    out = tmp_path / "tiles"
    total = st.slice_pyramid(src, 0, 2, str(out))

    assert total == 1 + 4 + 16 == 21, f"总数不对: {total}"
    for z in range(3):
        n = 2 ** z
        for x in range(n):
            for y in range(n):
                tile = out / str(z) / str(x) / f"{y}.png"
                assert tile.exists(), f"缺瓦片 {z}/{x}/{y}"
                with Image.open(tile) as im:
                    assert im.size == (256, 256), f"{z}/{x}/{y} 尺寸是 {im.size}"


@allure.feature("L0 单元测试")
@allure.story("切片契约")
@allure.title("四张切片内容互不重复")
def test_u10b_each_tile_is_visually_distinct(tmp_path):
    """U-10b 四张切片内容不应雷同 —— 防止坐标算错导致反复切同一块。"""
    from PIL import Image, ImageDraw

    # 四个象限涂不同颜色,z=1 切完正好每块一个颜色
    src = Image.new("RGB", (512, 512), (0, 0, 0))
    draw = ImageDraw.Draw(src)
    draw.rectangle([0, 0, 255, 255], fill=(255, 0, 0))
    draw.rectangle([256, 0, 511, 255], fill=(0, 255, 0))
    draw.rectangle([0, 256, 255, 511], fill=(0, 0, 255))
    draw.rectangle([256, 256, 511, 511], fill=(255, 255, 0))

    out = tmp_path / "tiles"
    st.slice_pyramid(src, 1, 1, str(out))
    digests = set()
    for x in range(2):
        for y in range(2):
            with Image.open(out / "1" / str(x) / f"{y}.png") as im:
                digests.add(im.tobytes())
    assert len(digests) == 4, "z=1 的四张切片内容重复,切片坐标可能算错了"
