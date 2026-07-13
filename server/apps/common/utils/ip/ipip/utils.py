# -*- coding: utf-8 -*-
#
"""基于 IPIP 数据库的 IP 城市查询工具。"""

import os

from django.conf import settings

from ipdb.city import City

__all__ = ['get_ip_city_by_ipip']
ipip_db: City | None = None


def init_ipip_db() -> None:
    """初始化 IPIP 城市数据库，重复调用时仅初始化一次。"""
    global ipip_db
    if ipip_db is not None:
        return

    ipip_db_path = os.path.join(settings.DATA_DIR, 'system', 'ipipfree.ipdb')
    if not os.path.exists(ipip_db_path):
        ipip_db_path = os.path.join(os.path.dirname(__file__), 'ipipfree.ipdb')
    if not os.path.exists(ipip_db_path):
        raise FileNotFoundError('IP Database not found, please run `python manage.py download_ip_db`')
    ipip_db = City(ipip_db_path)


def get_ip_city_by_ipip(ip: str) -> dict[str, str] | None:
    """根据 IP 地址查询城市与国家信息。

    Args:
        ip: 待查询的 IP 地址字符串。

    Returns:
        包含 city 和 country 名称的字典，查询失败时返回 None。
    """
    try:
        init_ipip_db()
    except Exception:
        return None
    try:
        info = ipip_db.find_info(ip, 'CN')
    except ValueError:
        return None
    if not info:
        return None
    return {'city': info.city_name, 'country': info.country_name}
