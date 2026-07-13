#!/usr/bin/env python
# -*- coding:utf-8 -*-
# project : xadmin-server
# filename : file
# author : ly_13
# date : 8/27/2024
"""文件下载工具模块。"""

from pathlib import Path

import requests


def download_file(src: str, path: str | Path) -> None:
    """下载远程文件到本地指定路径。

    Args:
        src: 远程文件 URL。
        path: 本地保存路径。
    """
    with requests.get(src, stream=True) as r:
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
