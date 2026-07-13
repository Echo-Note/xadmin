"""IP 地址解析与匹配工具模块。"""

import ipaddress
import socket
from ipaddress import ip_address, ip_network

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .geoip import get_ip_city_by_geoip
from .ipip import get_ip_city_by_ipip


def is_ip_address(address: str) -> bool:
    """判断字符串是否为合法 IP 地址。

    Args:
        address: 待检测的地址字符串。

    Returns:
        合法返回 True，否则返回 False。
    """
    try:
        ip_address(address)
    except ValueError:
        return False
    else:
        return True


def is_ip_network(ip: str) -> bool:
    """判断字符串是否为合法 IP 网段（如 192.168.1.0/24）。

    Args:
        ip: 待检测的网段字符串。

    Returns:
        合法返回 True，否则返回 False。
    """
    try:
        ip_network(ip)
    except ValueError:
        return False
    else:
        return True


def is_ip_segment(ip: str) -> bool:
    """判断字符串是否为 IP 区间格式（如 10.1.1.1-10.1.1.20）。

    Args:
        ip: 待检测的 IP 区间字符串。

    Returns:
        合法返回 True，否则返回 False。
    """
    if '-' not in ip:
        return False
    ip_address1, ip_address2 = ip.split('-')
    return is_ip_address(ip_address1) and is_ip_address(ip_address2)


def in_ip_segment(ip: str, ip_segment: str) -> bool:
    """判断 IP 是否在指定区间内。

    Args:
        ip: 待检测的 IP 地址。
        ip_segment: IP 区间字符串（如 10.1.1.1-10.1.1.20）。

    Returns:
        在区间内返回 True，否则返回 False。
    """
    ip1, ip2 = ip_segment.split('-')
    ip1 = int(ip_address(ip1))
    ip2 = int(ip_address(ip2))
    ip = int(ip_address(ip))
    return min(ip1, ip2) <= ip <= max(ip1, ip2)


def contains_ip(ip: str, ip_group: list[str]) -> bool:
    """判断 IP 是否包含在 IP 组中，支持单 IP、网段、区间及通配符。

    Args:
        ip: 待检测的 IP 地址。
        ip_group: IP 规则列表，可包含单 IP、网段、区间或 '*'。

    Returns:
        包含返回 True，否则返回 False。
    """
    if '*' in ip_group:
        return True

    for _ip in ip_group:
        if is_ip_address(_ip):
            # 192.168.10.1
            if ip == _ip:
                return True
        elif is_ip_network(_ip) and is_ip_address(ip):
            # 192.168.1.0/24
            if ip_address(ip) in ip_network(_ip):
                return True
        elif is_ip_segment(_ip) and is_ip_address(ip):
            # 10.1.1.1-10.1.1.20
            if in_ip_segment(ip, _ip):
                return True
        else:
            # address / host
            if ip == _ip:
                return True

    return False


def is_ip(ip: str, rule_value: str) -> bool:
    """根据规则判断 IP 是否匹配。

    支持通配符、网段、区间及前缀匹配。

    Args:
        ip: 待检测的 IP 地址。
        rule_value: 匹配规则字符串。

    Returns:
        匹配返回 True，否则返回 False。
    """
    if rule_value == '*':
        return True
    elif '/' in rule_value:
        network = ipaddress.ip_network(rule_value)
        return ip in network.hosts()
    elif '-' in rule_value:
        start_ip, end_ip = rule_value.split('-')
        start_ip = ipaddress.ip_address(start_ip)
        end_ip = ipaddress.ip_address(end_ip)
        return start_ip <= ip <= end_ip
    elif len(rule_value.split('.')) == 4:
        return ip == rule_value
    else:
        return ip.startswith(rule_value)


def get_ip_city(ip: str | None) -> str:
    """根据 IP 地址查询城市信息，优先使用 IPIP 数据库。

    Args:
        ip: IP 地址字符串。

    Returns:
        城市名称或国际化提示文案。
    """
    if not ip or not isinstance(ip, str):
        return _('Invalid address')
    if ':' in ip:
        return 'IPv6'

    info = get_ip_city_by_ipip(ip)
    if info:
        city = info.get('city', None)
        country = info.get('country')

        # 国内城市 并且 语言是中文就使用国内
        is_zh = settings.LANGUAGE_CODE.startswith('zh')
        if country == '中国' and is_zh:
            return city if city else get_ip_city_by_geoip(ip)
    return get_ip_city_by_geoip(ip)


def lookup_domain(domain: str) -> tuple[str | None, str]:
    """解析域名对应的 IP 地址。

    Args:
        domain: 域名字符串。

    Returns:
        元组 (IP 地址, 错误信息)，解析成功时错误信息为空字符串。
    """
    try:
        return socket.gethostbyname(domain), ''
    except Exception as e:
        return None, f'Cannot resolve {domain}: Unknown host, {e}'
