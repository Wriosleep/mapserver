# -*- coding: utf-8 -*-
"""
pytest 公共夹具与常量。

职责:
  1. 把项目根目录注入 sys.path —— 四个脚本平铺在根目录、没有包结构,
     测试要 import 它们必须先加路径。
  2. 暴露约定的路径常量。
  3. 探测瓦片服务器可达性:不可达时接口测试整组 skip 而不是 fail,
     保证「本机没开服务器」时其余测试仍然全绿。
"""

import hashlib
import os
import sys
from pathlib import Path

import pytest

# Windows 控制台默认是 GBK,断言信息里的中文会显示成乱码,这里统一切到 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

XYZ_DIR = PROJECT_ROOT / "tiles_xyz"
TMS_DIR = PROJECT_ROOT / "tiles_tms"
SRC_DIR = PROJECT_ROOT / "source"
WEB_DIR = PROJECT_ROOT / "web"

MAX_ZOOM = 5          # README 1.3.2: z0 ~ z5
TILE_COUNT = 1365     # sum(4^z), z=0..5 = (4^6 - 1) / 3

# 默认指向 README 1.3 记录的虚拟机;用环境变量可覆盖:
#   TILE_BASE_URL=http://127.0.0.1/tiles pytest
DEFAULT_BASE_URL = "http://192.168.247.129/tiles"


def md5_file(path, chunk=1 << 16):
    """流式计算文件 MD5。瓦片很小,但保持能处理大文件的写法。"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


@pytest.fixture(scope="session")
def tile_server():
    """接口测试基地址。探测不通就整组 skip,而不是报一堆红。"""
    import requests

    url = os.environ.get("TILE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    try:
        requests.head(f"{url}/0/0/0.png", timeout=3)
    except Exception as exc:  # 任何连接层问题都视为服务未就绪
        pytest.skip(f"瓦片服务器 {url} 不可达,跳过接口测试"
                    f"(用环境变量 TILE_BASE_URL 指定地址): {exc}")
    return url
