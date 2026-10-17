# -*- coding: utf-8 -*-
"""
缺陷回归用例集 —— 把「已确认存在的缺陷」固定成可重复执行的断言。

用法上有个讲究:这里不直接改代码,而是用 xfail 把缺陷「钉」在测试里。
  * 缺陷还在 -> 用例标记为 xfail(预期失败),报告里一眼能看到;
  * 有人修好了 -> 用例变成 XPASS,提醒你把 xfail 标记摘掉,转成正式断言。

这就是缺陷回归测试该有的闭环:问题被记录、可追踪,修复有明确的验收信号。
"""

import re

import allure
import pytest

import download_tiles as dl
from conftest import PROJECT_ROOT


@pytest.mark.xfail(reason="已知缺陷 D-01:断点续传只判文件非空,不校验内容")
@allure.feature("缺陷回归")
@allure.story("D-01 断点续传")
@allure.title("损坏文件不应被判定为已完成")
def test_d01_resume_treats_corrupt_file_as_complete(tmp_path):
    """D-01 断点续传的判据太弱。

    download_tiles.py 的 fetch_one() 只检查「文件存在且字节数 > 0」就跳过重下。
    但下载失败时服务端常常返回 200 + 一段 HTML 错误页 —— 那也是非空文件,
    于是会被永久当成「已完成」,并且此后再也不会重试(重跑脚本依然跳过)。

    期望行为:内容不是合法 PNG 时必须重新下载。
    当前行为:直接返回 "skip",所以本用例 xfail。

    影响:一次网络抖动就可能往瓦片集里埋进一张假数据,而且不报错。
    """
    outdir = tmp_path / "tiles_xyz"
    (outdir / "0" / "0").mkdir(parents=True)
    corrupt = outdir / "0" / "0" / "0.png"
    corrupt.write_bytes(b"<html><body>403 Forbidden</body></html>")

    result = dl.fetch_one("https://example.invalid/{z}/{x}/{y}.png",
                          str(outdir), 0, 0, 0, retries=1)
    assert result != "skip", "损坏文件被判定为已完成,永远不会被重新下载"


@pytest.mark.xfail(reason="已知缺陷 D-06:README 实测标注 24 线程,脚本默认 --workers=8")
@allure.feature("缺陷回归")
@allure.story("D-06 文档一致性")
@allure.title("并发默认值与 README 实测口径一致")
def test_d06_worker_default_matches_readme():
    """D-06 文档与实现不一致。

    README 1.4.1 的实测记录写的是「1280 张瓦片 / 24 线程 / 535 秒」,
    而 download_tiles.py 里 --workers 的默认值是 8。照着 README 复现的人,
    不显式传参就得不到文档里描述的那组性能数据。

    期望行为:文档记录的口径与脚本默认值一致(或文档注明需手动指定)。
    """
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    source = (PROJECT_ROOT / "download_tiles.py").read_text(encoding="utf-8")

    assert "24 线程" in readme, "README 里的并发实测说明被改动了,需同步本用例"
    match = re.search(r'"--workers",\s*type=int,\s*default=(\d+)', source)
    assert match, "没找到 --workers 的默认值定义"

    assert int(match.group(1)) == 24, "脚本默认并发数与文档记录的实测口径不一致"
