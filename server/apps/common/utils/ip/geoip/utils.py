# -*- coding: utf-8 -*-
#
"""基于 GeoLite2 数据库的 IP 城市查询工具。"""

import ipaddress
import os

import geoip2.database
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from geoip2.errors import GeoIP2Error

__all__ = ['get_ip_city_by_geoip']
reader: geoip2.database.Reader | None = None


def init_ip_reader() -> None:
    """初始化 GeoIP2 数据库读取器，重复调用时仅初始化一次。"""
    global reader
    if reader:
        return

    path = os.path.join(settings.DATA_DIR, 'system', 'GeoLite2-City.mmdb')
    if not os.path.exists(path):
        path = os.path.join(os.path.dirname(__file__), 'GeoLite2-City.mmdb')
    if not os.path.exists(path):
        raise FileNotFoundError('IP Database not found, please run `python manage.py download_ip_db`')

    reader = geoip2.database.Reader(path)


def get_ip_city_by_geoip(ip: str) -> str:
    """根据 IP 地址查询城市名称。

    私有地址返回局域网标识，无效地址返回错误提示，查询失败返回未知。

    Args:
        ip: 待查询的 IP 地址字符串。

    Returns:
        城市名称或对应的国际化提示文案。
    """
    try:
        init_ip_reader()
    except Exception:
        return _("Unknown")

    try:
        is_private = ipaddress.ip_address(ip.strip()).is_private
        if is_private:
            return _('LAN')
    except ValueError:
        return _("Invalid ip")

    try:
        response = reader.city(ip)
    except GeoIP2Error:
        return _("Unknown")

    city_names = response.city.names or {}
    lang = settings.LANGUAGE_CODE[:2]
    if lang == 'zh':
        lang = 'zh-CN'
    city = city_names.get(lang, _("Unknown"))
    return city
