# -*- coding: utf-8 -*-
"""
L2 接口测试 —— HTTP 层,针对 VM 上的 Apache。

地址来自 conftest 的 tile_server 夹具(默认 http://192.168.247.129/tiles,
可用环境变量 TILE_BASE_URL 覆盖)。服务器不可达时整组 skip,不会制造噪声。

断言重点放在两处:
  * README 1.4.3 强调的「不能只看 200」—— Server 头必须是 Apache,
    否则可能是别的服务(或另一个虚拟主机)在答话。
  * 端到端保真 —— 服务器吐出来的字节,必须和本地 tiles_tms 上那份逐字节一致。
"""

import hashlib

import allure
import pytest
import requests

from conftest import TMS_DIR, XYZ_DIR, md5_file

TIMEOUT = 10


# ---------------------------------------------------------------- 基础可用性

@allure.feature("L2 接口测试")
@allure.story("基础可用性")
@allure.title("z=0 根瓦片可访问")
def test_a01_root_tile_is_served(tile_server):
    """A-01 最基础的一张(z=0)应当可访问。"""
    r = requests.get(f"{tile_server}/0/0/0.png", timeout=TIMEOUT)
    assert r.status_code == 200, f"期望 200,实际 {r.status_code}"


@allure.feature("L2 接口测试")
@allure.story("基础可用性")
@allure.title("不存在的级别返回 404")
def test_a02_missing_tile_returns_404(tile_server):
    """A-02(负向) 不存在的级别应返回 404,不能是 200 或 500。"""
    r = requests.get(f"{tile_server}/9/0/0.png", timeout=TIMEOUT)
    assert r.status_code == 404, f"期望 404,实际 {r.status_code}"


# ---------------------------------------------------------------- 响应头契约

@allure.feature("L2 接口测试")
@allure.story("响应头契约")
@allure.title("Content-Type 为 image/png")
def test_a03_content_type_is_png(tile_server):
    """A-03 Content-Type 必须是 image/png,否则浏览器可能不当作图像处理。"""
    r = requests.get(f"{tile_server}/0/0/0.png", timeout=TIMEOUT)
    assert r.headers.get("Content-Type", "").startswith("image/png"), \
        f"Content-Type 是 {r.headers.get('Content-Type')!r}"


@allure.feature("L2 接口测试")
@allure.story("响应头契约")
@allure.title("Content-Length 与实际字节数一致")
def test_a04_content_length_matches_body(tile_server):
    """A-04 声明长度必须等于实际字节数,且开头是 PNG 魔数。"""
    r = requests.get(f"{tile_server}/0/0/0.png", timeout=TIMEOUT)
    assert int(r.headers["Content-Length"]) == len(r.content)
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n", "响应体不是 PNG,可能是错误页"


@allure.feature("L2 接口测试")
@allure.story("响应头契约")
@allure.title("Server 头为 Apache")
def test_a05_server_header_is_apache(tile_server):
    """A-05 确认是 Apache 在答话 —— README 1.4.3 的「不能只看 200」。"""
    r = requests.head(f"{tile_server}/0/0/0.png", timeout=TIMEOUT)
    server = r.headers.get("Server", "")
    assert "Apache" in server, f"Server 头是 {server!r},可能被别的服务接管了"


@allure.feature("L2 接口测试")
@allure.story("响应头契约")
@allure.title("HEAD 与 GET 状态码和长度一致")
def test_a06_head_and_get_agree(tile_server):
    """A-06 HEAD 与 GET 的状态码、Content-Length 必须一致。"""
    url = f"{tile_server}/0/0/0.png"
    head = requests.head(url, timeout=TIMEOUT)
    get = requests.get(url, timeout=TIMEOUT)
    assert head.status_code == get.status_code == 200
    assert head.headers.get("Content-Length") == get.headers.get("Content-Length")


# ---------------------------------------------------------------- 端到端保真

@allure.feature("L2 接口测试")
@allure.story("端到端保真")
@allure.title("服务器字节与本地瓦片逐字节一致")
def test_a07_served_bytes_match_local_disk(tile_server):
    """A-07(核心) 端到端保真:服务器返回的字节 == 本地 tiles_tms 上的文件。

    这条用例同时验证了「传输没有损坏」和「部署的就是转换后的产物」两件事。
    """
    local = TMS_DIR / "1" / "0" / "0.png"
    if not local.exists():
        pytest.skip("本地缺 tiles_tms/1/0/0.png,无法比对")

    r = requests.get(f"{tile_server}/1/0/0.png", timeout=TIMEOUT)
    assert r.status_code == 200
    assert hashlib.md5(r.content).hexdigest() == md5_file(local), \
        "服务器上的瓦片与本地产物不一致(部署的可能是旧数据)"


@allure.feature("L2 接口测试")
@allure.story("端到端保真")
@allure.title("TMS 行号指向正确的源瓦片")
def test_a08_tms_path_semantics_are_correct(tile_server):
    """A-08 TMS 语义:请求 TMS 的 1/0/0(南半球)内容应等于 XYZ 的 1/0/1。

    这是把「翻转公式」从文件系统一路验到 HTTP 出口 —— 链路最长的一条断言。
    """
    src = XYZ_DIR / "1" / "0" / "1.png"
    if not src.exists():
        pytest.skip("本地缺 tiles_xyz/1/0/1.png,无法比对")

    r = requests.get(f"{tile_server}/1/0/0.png", timeout=TIMEOUT)
    assert r.status_code == 200
    assert hashlib.md5(r.content).hexdigest() == md5_file(src), \
        "TMS 行号没有指向正确的源瓦片,地图会上下颠倒"


# ---------------------------------------------------------------- 边界 / 安全

@allure.feature("L2 接口测试")
@allure.story("边界与安全")
@allure.title("z=5 最右上角瓦片存在")
def test_a09_max_zoom_corner_tile(tile_server):
    """A-09 边界坐标:最右上角一张必须存在(z=5 时 x=y=31)。"""
    r = requests.get(f"{tile_server}/5/31/31.png", timeout=TIMEOUT)
    assert r.status_code == 200, f"期望 200,实际 {r.status_code}"


@pytest.mark.parametrize("payload", [
    "/../etc/passwd",
    "/%2e%2e/%2e%2e/etc/passwd",
    "/..%2f..%2fetc%2fpasswd",
    "/0/0/../../../etc/passwd",
])
@allure.feature("L2 接口测试")
@allure.story("边界与安全")
@allure.title("路径穿越被拦截（{payload}）")
def test_a10_path_traversal_is_blocked(tile_server, payload):
    """A-10(安全) 目录穿越不得成功读到系统文件。

    Options FollowSymLinks 打开后,这类请求要格外确认一遍。
    """
    r = requests.get(tile_server + payload, timeout=TIMEOUT)
    assert r.status_code != 200 or b"root:" not in r.content, \
        f"路径穿越成功: {payload}"


@allure.feature("L2 接口测试")
@allure.story("边界与安全")
@allure.title("扩展名大小写敏感返回 404")
def test_a11_extension_case_sensitivity(tile_server):
    """A-11 Linux 文件系统区分大小写,大写扩展名应 404(记录服务端行为)。"""
    r = requests.get(f"{tile_server}/0/0/0.PNG", timeout=TIMEOUT)
    assert r.status_code == 404, \
        f"返回 {r.status_code},服务端大小写行为与预期不符,需复核"


@allure.feature("L2 接口测试")
@allure.story("稳定性")
@allure.title("同一 URL 重复请求 30 次全部 200")
def test_a12_repeated_requests_are_stable(tile_server):
    """A-12 稳定性:同一 URL 重复请求不得出现偶发失败。"""
    url = f"{tile_server}/2/1/1.png"
    codes = {requests.get(url, timeout=TIMEOUT).status_code for _ in range(30)}
    assert codes == {200}, f"重复请求出现异常状态码: {codes}"


@allure.feature("L2 接口测试")
@allure.story("跨机一致性")
@allure.title("两个入口返回相同字节")
def test_a13_cross_host_consistency(tile_server):
    """A-13 跨机一致:127.0.0.1 与 VM 地址返回同一份字节。

    需要额外设置 TILE_BASE_URL_ALT(例如 http://127.0.0.1/tiles)才会执行。
    """
    import os
    alt = os.environ.get("TILE_BASE_URL_ALT")
    if not alt:
        pytest.skip("未设置 TILE_BASE_URL_ALT,跳过跨机比对")

    a = requests.get(f"{tile_server}/0/0/0.png", timeout=TIMEOUT).content
    b = requests.get(f"{alt.rstrip('/')}/0/0/0.png", timeout=TIMEOUT).content
    assert hashlib.md5(a).hexdigest() == hashlib.md5(b).hexdigest(), \
        "两台入口返回的瓦片不一致"
