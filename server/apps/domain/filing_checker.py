"""ICP / 公安备案预检测模块。

提供域名首页备案号悬挂检测功能：
1. DNS 检查：判断域名是否存在 www 子域名解析记录
2. HTTP 抓取：若存在 www 记录，通过 HTTPS（含降级策略）请求首页
3. DOM 解析：用 BeautifulSoup 精确定位页脚节点，自动跳过 script/style
4. 规则匹配：用精确正则同时匹配 ICP 备案号、公安备案号

防脏数据策略：
- DOM 层：BeautifulSoup get_text() 自动跳过 <script>/<style>/<template>，
  避免匹配到 JS 代码里的字符串（如 var icp = '渝ICP备...'）
- CSS 层：用 CSS 选择器精确定位 <footer>/.footer/#footer 等真实页脚节点
- 正则层：精确省份简称单字 + 负向后行断言 (?<![\\u4e00-\\u9fa5])
- 实体层：BeautifulSoup 自动解码 HTML 实体（&copy; &nbsp; 等）

从 apps.asset.filing_checker 迁移而来。
"""

from __future__ import annotations

import logging
import re
import socket
from datetime import datetime
from typing import TYPE_CHECKING, Any

import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from apps.domain.choices import IcpCheckStatusChoices, IcpFilingStatusChoices

if TYPE_CHECKING:
    from apps.domain.models import Domain, Filing

logger = logging.getLogger(__name__)

# 省/直辖市/自治区/特别行政区简称（单字）
# 顺序：直辖市 → 省 → 自治区 → 特别行政区
PROVINCE_PREFIX = '京津沪渝冀晋辽吉黑苏浙皖闽赣鲁豫鄂湘粤琼川贵云陕甘青蒙桂藏宁新港澳台'

# ICP 备案号正则：[省简称]ICP备/证<数字>号[-<数字>]
# 关键点：
#   1. (?<![\\u4e00-\\u9fa5]) 负向后行断言，确保省简称前不是汉字（如 "公司渝ICP备" 中的 "渝" 不会被匹配）
#   2. PROVINCE_PREFIX 精确列出 31+3 个省级行政区简称单字，避免误匹配
ICP_NUMBER_PATTERN = re.compile(rf'(?<![\u4e00-\u9fa5])[{PROVINCE_PREFIX}]ICP(?:备|证)\d+(?:-\d+)?号')

# 公安备案号正则：[省简称]公网安备<数字>号（"公网安备" 与数字间可有可选空白）
# 示例：京公网安备 110100000001号 / 京公网安备110100000001号
PS_NUMBER_PATTERN = re.compile(rf'(?<![\u4e00-\u9fa5])[{PROVINCE_PREFIX}]公网安备\s*\d+(?:-\d+)?号')

# HTTP 请求超时（秒）
HTTP_TIMEOUT = 15
# 响应长度上限（1MB），防止拖取大文件
MAX_RESPONSE_SIZE = 1024 * 1024

# 页脚 CSS 选择器（按优先级从高到低）
# 1. HTML5 <footer> 标签最可靠
# 2. class/id 包含 footer/beian/copyright/bottom 的元素
# 3. class 包含 banquan（版权拼音）/ link（友情链接区常含备案号）
FOOTER_CSS_SELECTORS = [
    'footer',
    '[class*=footer]',
    '[id*=footer]',
    '[class*=beian]',
    '[id*=beian]',
    '[class*=copyright]',
    '[id*=copyright]',
    '[class*=banquan]',
    '[class*=bottom-info]',
    '[class*=site-info]',
    '[class*=foot-link]',
    '[class*=links]',
]

# 解析 HTML 时需要显式移除的标签（get_text 虽会跳过，显式 decompose 更彻底）
_NOISE_TAGS = ['script', 'style', 'noscript', 'template', 'svg', 'iframe']


def _check_www_dns(domain_name: str) -> bool:
    """检测域名是否存在 www 子域名的 DNS 解析记录。

    尝试解析 www.{domain_name} 的 A 和 AAAA 记录，
    若至少有一个地址返回则认为存在 www 解析记录。

    Args:
        domain_name: 域名，如 example.com。

    Returns:
        True 表示存在 www 解析记录，False 表示不存在。
    """
    www_host = f'www.{domain_name}'
    try:
        # 同时尝试 IPv4 和 IPv6
        socket.getaddrinfo(www_host, 80, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return True
    except socket.gaierror:
        return False
    except OSError as e:
        logger.warning('DNS 查询异常 %s: %s', www_host, e)
        return False


def _fetch_page(url: str) -> tuple[str | None, bool]:
    """获取指定 URL 的网页内容，带多级降级策略。

    尝试顺序：
    1. HTTPS + SSL 校验
    2. HTTPS + 跳过 SSL 校验（证书过期/不匹配时回退）
    3. HTTP 明文 + 不跟随重定向（避免被重定向回 HTTPS）
    4. HTTP 明文 + 跟随重定向 + verify=False（跟随到 HTTPS 时跳过证书校验）

    Args:
        url: 要访问的完整 URL。

    Returns:
        (网页文本内容, 是否使用了HTTPS) 元组，失败返回 (None, False)。
    """
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/125.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    http_url = url.replace('https://', 'http://', 1) if url.startswith('https://') else url

    # 尝试方案：(url, verify, allow_redirects, is_https)
    attempts = [
        (url, True, True, True),  # HTTPS + 校验
        (url, False, True, True),  # HTTPS + 跳过校验
        (http_url, False, False, False),  # HTTP 不跟随重定向
        (http_url, False, True, False),  # HTTP 跟随重定向 + verify=False
    ]

    for target_url, verify, allow_redirects, is_https in attempts:
        try:
            resp = requests.get(
                target_url,
                headers=headers,
                timeout=HTTP_TIMEOUT,
                allow_redirects=allow_redirects,
                verify=verify,
            )

            if 300 <= resp.status_code < 400:
                logger.debug('重定向跳过 %s → %s', target_url, resp.headers.get('Location', '?'))
                continue

            resp.raise_for_status()

            content_type = resp.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                logger.info('非 HTML 响应，跳过页脚检测: %s → %s', target_url, content_type)
                return None, is_https

            content = resp.content[:MAX_RESPONSE_SIZE]
            encoding = resp.apparent_encoding or 'utf-8'
            text = content.decode(encoding, errors='replace')
            return text, is_https
        except requests.exceptions.SSLError:
            logger.debug('SSL 异常 %s (verify=%s)', target_url, verify)
            continue
        except requests.RequestException as e:
            logger.debug('请求失败 %s: %s', target_url, type(e).__name__)
            continue

    logger.warning('所有请求方案均失败: %s', url)
    return None, False


def _extract_footer_text(html_text: str) -> str:
    """从 HTML 中精确提取页脚区域的文本内容。

    使用 BeautifulSoup 进行 DOM 解析，相比正则方案的优势：
    1. CSS 选择器精确定位 <footer>/.footer/#footer 等真实页脚节点
    2. get_text() 自动跳过 <script>/<style>/<template>，不误匹配 JS 代码
    3. HTML 实体自动解码（&copy; &nbsp; 等）
    4. 处理畸形 HTML 容错好（国内站点 HTML 质量参差不齐）

    提取策略（按优先级）：
    a. CSS 选择器定位页脚节点 → 取文本
    b. 找不到时，扫描所有文本节点中含备案关键词的节点及其父级
    c. 最后回退到 body 文本末尾 1000 字符

    Args:
        html_text: 完整的 HTML 文本。

    Returns:
        提取到的页脚区域文本。
    """
    if not html_text:
        return ''

    # 用 lxml 后端（C 实现，快且容错好）
    soup = BeautifulSoup(html_text, 'lxml')

    # 显式移除噪声标签（script/style 等），避免 get_text 误包含
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    # 策略 a: CSS 选择器定位页脚
    for selector in FOOTER_CSS_SELECTORS:
        elements = soup.select(selector)
        if elements:
            # 取最后一个匹配元素（通常是最底部的真正页脚）
            text = elements[-1].get_text(separator='\n', strip=True)
            if text:
                return text

    # 策略 b: 扫描含备案关键词的文本节点
    beian_keywords = ['ICP备', 'ICP证', '公网安备', '版权所有', 'copyright', 'Copyright']
    for tag in soup.find_all(string=True):
        text = tag.strip()
        if any(kw in text for kw in beian_keywords):
            # 返回该文本节点所在父级标签的全部文本
            parent = tag.parent
            if parent:
                parent_text = parent.get_text(separator='\n', strip=True)
                if parent_text:
                    return parent_text

    # 策略 c: 回退到 body 文本末尾
    body = soup.find('body') or soup
    full_text = body.get_text(separator='\n', strip=True)
    return full_text[-1000:] if len(full_text) > 1000 else full_text


def _detect_filing_numbers(text: str) -> tuple[list[str], list[str]]:
    """从文本中检测 ICP 备案号和公安备案号。

    使用精确正则匹配，确保不产生脏数据：
    - ICP 备案号格式：[省简称]ICP备/证<数字>号[-<数字>]
    - 公安备案号格式：[省简称]公网安备<数字>号（"公网安备" 与数字间可有可选空白）

    Args:
        text: 待检测的文本内容（HTML 或纯文本均可）。

    Returns:
        (icp_numbers, ps_numbers) 元组，分别去重保序后的备案号列表。
    """
    if not text:
        return [], []

    # dict.fromkeys 去重保序
    icp_raw = ICP_NUMBER_PATTERN.findall(text)
    ps_raw = PS_NUMBER_PATTERN.findall(text)

    icp = list(dict.fromkeys(icp_raw))
    # 公安备案号规范化：去除 "公网安备" 与数字之间的空白
    ps = list(dict.fromkeys(re.sub(r'\s+', '', p) for p in ps_raw))
    return icp, ps


def _check_ssl_certificate(domain_name: str) -> dict[str, Any] | None:
    """获取域名 SSL 证书详细信息。

    通过 TLS 连接 www.{domain_name}:443 获取 DER 格式证书，
    用 cryptography.x509 解析主体/颁发者/有效期/SAN 等字段。

    Args:
        domain_name: 域名，如 example.com。

    Returns:
        证书信息字典，包含以下键：
        - subject_cn / subject_o / subject_ou: 主体信息
        - issuer_cn / issuer_o: 颁发者信息
        - serial_number: 序列号（十六进制字符串）
        - signature_algorithm: 签名算法
        - not_before / not_after: 有效期（datetime 对象）
        - san_domains: 备用域名列表
        - is_valid: 是否在有效期内
        检测失败返回 None。
    """
    import socket
    import ssl as ssl_module

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import ExtensionOID, NameOID

    hostname = f'www.{domain_name}'

    try:
        # 建立 TLS 连接获取证书
        ctx = ssl_module.create_default_context()
        with socket.create_connection((hostname, 443), timeout=HTTP_TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)

                # 获取完整证书链（Python 3.13 公开 API，3.12 私有 API）
                der_chain: list[bytes] | None = None
                get_chain = getattr(ssock, 'get_unverified_chain', None)
                if get_chain is None:
                    get_chain = getattr(getattr(ssock, '_sslobj', None), 'get_unverified_chain', None)
                if get_chain is not None:
                    try:
                        der_chain = list(get_chain())
                    except Exception:
                        der_chain = None

        if not der_cert:
            logger.debug('未获取到证书数据: %s', hostname)
            return None

        cert = x509.load_der_x509_certificate(der_cert)

        # PEM 格式证书（用于部署）
        from cryptography.hazmat.primitives import serialization

        certificate_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')

        # 中间证书链 PEM（拼接所有非终端证书）
        intermediate_pem = ''
        if der_chain and len(der_chain) > 1:
            parts: list[str] = []
            for der_bytes in der_chain[1:]:
                try:
                    chain_cert = x509.load_der_x509_certificate(der_bytes)
                    parts.append(chain_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8'))
                except Exception:
                    pass
            intermediate_pem = ''.join(parts)

        # 解析主体（Subject）
        subject = cert.subject
        subject_cn = _get_name_attr(subject, NameOID.COMMON_NAME)
        subject_o = _get_name_attr(subject, NameOID.ORGANIZATION_NAME)
        subject_ou = _get_name_attr(subject, NameOID.ORGANIZATIONAL_UNIT_NAME)

        # 解析颁发者（Issuer）
        issuer = cert.issuer
        issuer_cn = _get_name_attr(issuer, NameOID.COMMON_NAME)
        issuer_o = _get_name_attr(issuer, NameOID.ORGANIZATION_NAME)

        # 解析 SAN（Subject Alternative Names）
        san_domains: list[str] = []
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            san_domains = san_ext.value.get_values_for_type(x509.DNSName)
        except x509.ExtensionNotFound:
            pass

        # 有效期（优先使用 timezone-aware 版本，cryptography 42+）
        not_before = getattr(cert, 'not_valid_before_utc', None) or cert.not_valid_before
        not_after = getattr(cert, 'not_valid_after_utc', None) or cert.not_valid_after

        # 签名算法
        sig_algo = cert.signature_hash_algorithm
        sig_algo_name = sig_algo.name if sig_algo else None

        # 判断是否在有效期内
        from datetime import UTC, datetime

        now_utc = datetime.now(UTC)
        is_valid = not_before <= now_utc <= not_after

        return {
            'subject_cn': subject_cn,
            'subject_o': subject_o,
            'subject_ou': subject_ou,
            'issuer_cn': issuer_cn,
            'issuer_o': issuer_o,
            'serial_number': format(cert.serial_number, 'x'),
            'signature_algorithm': sig_algo_name,
            'not_before': not_before,
            'not_after': not_after,
            'san_domains': san_domains,
            'is_valid': is_valid,
            'fingerprint': cert.fingerprint(hashes.SHA256()).hex(),
            'certificate_pem': certificate_pem,
            'intermediate_pem': intermediate_pem,
        }
    except (ssl_module.SSLError, OSError) as e:
        logger.debug('SSL 证书检测失败 %s: %s', hostname, e)
        return None
    except Exception as e:
        logger.warning('SSL 证书解析异常 %s: %s', hostname, e)
        return None


def _get_name_attr(name: Any, oid: Any) -> str | None:
    """从 x509.Name 中获取指定 OID 的属性值。

    Args:
        name: x509.Name 对象（subject 或 issuer）。
        oid: NameOID 常量。

    Returns:
        属性值字符串，不存在返回 None。
    """
    attrs = name.get_attributes_for_oid(oid)
    return attrs[0].value if attrs else None


def run_icp_precheck(domain_name: str) -> dict[str, Any]:
    """对指定域名执行备案号悬挂预检测（ICP + 公安）。

    完整的检测流程：
    1. 检查 www 子域名 DNS 解析
    2. 若存在 www 解析，通过 HTTPS 访问首页（含降级策略）
    3. 提取页脚区域文本
    4. 在页脚文本中匹配 ICP 备案号和公安备案号；页脚未找到则回退搜索全页 HTML

    Args:
        domain_name: 域名，如 example.com。

    Returns:
        包含以下键的检测结果字典：
        - has_www_record: bool
        - footer_content: str | None
        - detected_icp_numbers: list[str]  （检测到的 ICP 备案号）
        - detected_ps_numbers: list[str]  （检测到的公安备案号）
        - detected_numbers: list[str]     （兼容旧字段，等同 detected_icp_numbers）
        - check_status: str（IcpCheckStatusChoices 枚举值）
        - conclusion: str
        - check_time: str (ISO 格式)
        - used_https: bool（是否通过 HTTPS 成功访问）
    """
    result: dict[str, Any] = {
        'has_www_record': False,
        'footer_content': None,
        'detected_icp_numbers': [],
        'detected_ps_numbers': [],
        'detected_numbers': [],
        'check_status': IcpCheckStatusChoices.NOT_CHECKED,
        'conclusion': '',
        'check_time': timezone.now().isoformat(),
        'used_https': False,
    }

    # 步骤 1: DNS 检查
    result['has_www_record'] = _check_www_dns(domain_name)

    if not result['has_www_record']:
        result['check_status'] = IcpCheckStatusChoices.NO_WWW_RECORD
        result['conclusion'] = f'域名 {domain_name} 未配置 www 解析记录，已跳过首页页脚检测。'
        return result

    # 步骤 2: HTTP 抓取（含 HTTPS→HTTP 降级）
    www_url = f'https://www.{domain_name}/'
    html_text, used_https = _fetch_page(www_url)
    result['used_https'] = used_https

    if html_text is None:
        result['check_status'] = IcpCheckStatusChoices.CHECK_FAILED
        result['conclusion'] = f'无法访问 https://www.{domain_name}/，请确认网站是否正常运行。'
        return result

    # 步骤 3: 提取页脚文本
    footer_text = _extract_footer_text(html_text)
    result['footer_content'] = footer_text

    # 步骤 4: 检测备案号
    # 4a. 优先在页脚区域匹配
    icp_nums, ps_nums = _detect_filing_numbers(footer_text)

    # 4b. 页脚未找到任一类时，搜索全页 HTML
    #     （覆盖 SPA 预埋在 script/meta/JSON-LD 中的备案号）
    if not icp_nums and not ps_nums:
        icp_nums, ps_nums = _detect_filing_numbers(html_text)

    result['detected_icp_numbers'] = icp_nums
    result['detected_ps_numbers'] = ps_nums
    result['detected_numbers'] = icp_nums  # 兼容旧字段

    # 判断检测状态：找到 ICP 或公安任一即视为通过
    if icp_nums or ps_nums:
        result['check_status'] = IcpCheckStatusChoices.PASSED
        parts = []
        if icp_nums:
            parts.append('ICP 备案号：' + '、'.join(icp_nums))
        if ps_nums:
            parts.append('公安备案号：' + '、'.join(ps_nums))
        result['conclusion'] = '首页已检测到备案号——' + '；'.join(parts) + '。'
    else:
        result['check_status'] = IcpCheckStatusChoices.SUSPECTED_MISSING
        result['conclusion'] = f'首页页脚未检测到 ICP/公安备案号，建议人工确认 https://www.{domain_name}/。'

    return result


def apply_precheck_result(
    filing: Filing,
    result: dict[str, Any],
    check_time: datetime | None = None,
) -> list[str]:
    """将预检测结果回写到 Filing 记录（不调用 save，由调用方保存）。

    统一处理检测元信息、ICP/公安备案号与状态联动、Domain SSL 状态同步，
    避免 tasks.py 和 views.py 中重复编写相同的回写逻辑。

    回写规则：
    - 检测元信息：icp_has_www_record / icp_check_status / icp_check_conclusion /
      icp_check_time / icp_footer_content（始终更新）
    - ICP 备案号：检测到 → 填入 icp_number，状态置 filed
                  未悬挂(suspected_missing) → 状态置 not_filed
    - 公安备案号：同 ICP 逻辑
    - Domain.is_ssl_enabled：有 www 记录时根据 used_https 同步更新

    Args:
        filing: Filing 模型实例（需已关联 domain）。
        result: run_icp_precheck() 返回的检测结果字典。
        check_time: 检测时间，默认使用 timezone.now()。

    Returns:
        Filing 需要更新的字段名列表（用于 save(update_fields=...)）。
        调用方负责执行 filing.save() 和 filing.domain.save()。
    """
    if check_time is None:
        check_time = timezone.now()

    # 1. 检测元信息
    filing.icp_has_www_record = result['has_www_record']
    filing.icp_check_status = result['check_status']
    filing.icp_check_conclusion = result['conclusion']
    filing.icp_check_time = check_time
    if result.get('footer_content') is not None:
        filing.icp_footer_content = result['footer_content']

    update_fields = [
        'icp_has_www_record',
        'icp_check_status',
        'icp_check_conclusion',
        'icp_check_time',
        'icp_footer_content',
        'icp_number',
        'icp_status',
        'ps_filing_number',
        'ps_status',
    ]

    # 2. ICP 备案号和状态联动
    icp_nums = result.get('detected_icp_numbers', [])
    if icp_nums:
        filing.icp_number = icp_nums[0]
        filing.icp_status = IcpFilingStatusChoices.FILED
    elif result['check_status'] == IcpCheckStatusChoices.SUSPECTED_MISSING:
        # 网站可访问但未检测到备案号 → 标记为未悬挂
        filing.icp_status = IcpFilingStatusChoices.NOT_FILED

    # 3. 公安备案号和状态联动
    ps_nums = result.get('detected_ps_numbers', [])
    if ps_nums:
        filing.ps_filing_number = ps_nums[0]
        filing.ps_status = IcpFilingStatusChoices.FILED
    elif result['check_status'] == IcpCheckStatusChoices.SUSPECTED_MISSING:
        filing.ps_status = IcpFilingStatusChoices.NOT_FILED

    # 4. Domain SSL 状态同步（有 www 记录时才更新）
    if result.get('has_www_record'):
        filing.domain.is_ssl_enabled = result.get('used_https', False)

        # HTTPS 可用时检测 SSL 证书详情
        if result.get('used_https'):
            ssl_info = _check_ssl_certificate(filing.domain.domain_name)
            result['ssl_certificate'] = ssl_info

            if ssl_info:
                # 同步 Domain.ssl_expire_time（冗余字段，方便列表展示）
                filing.domain.ssl_expire_time = ssl_info['not_after'].date()

                # 创建/更新 SslCertificate 记录
                _sync_ssl_certificate_record(filing.domain, ssl_info, check_time)

    return update_fields


def _sync_ssl_certificate_record(
    domain: Domain,
    ssl_info: dict[str, Any],
    check_time: datetime,
) -> None:
    """创建或更新 SslCertificate 记录，并关联到 Domain（直接 save）。

    相同证书（SHA256 指纹相同）只存一条，多个 Domain 关联到同一条记录。

    Args:
        domain: Domain 实例。
        ssl_info: _check_ssl_certificate() 返回的证书信息字典（含 fingerprint）。
        check_time: 检测时间。
    """
    from apps.domain.models import SslCertificate

    # 用指纹去重：相同证书只存一条
    cert, created = SslCertificate.objects.update_or_create(
        fingerprint=ssl_info['fingerprint'],
        defaults={
            'subject_cn': ssl_info['subject_cn'],
            'subject_o': ssl_info['subject_o'],
            'subject_ou': ssl_info['subject_ou'],
            'issuer_cn': ssl_info['issuer_cn'],
            'issuer_o': ssl_info['issuer_o'],
            'serial_number': ssl_info['serial_number'],
            'signature_algorithm': ssl_info['signature_algorithm'],
            'not_before': ssl_info['not_before'],
            'not_after': ssl_info['not_after'],
            'san_domains': ssl_info['san_domains'],
            'is_valid': ssl_info['is_valid'],
            'check_time': check_time,
            'certificate_pem': ssl_info.get('certificate_pem'),
            'intermediate_pem': ssl_info.get('intermediate_pem'),
        },
    )

    # 关联 Domain 到证书记录（相同证书自动共用）
    domain.ssl_certificate = cert

    logger.debug(
        'SSL 证书记录%s: %s → %s (到期: %s, 指纹: %s...)',
        '创建' if created else '更新',
        domain.domain_name,
        ssl_info['subject_cn'],
        ssl_info['not_after'].strftime('%Y-%m-%d'),
        ssl_info['fingerprint'][:16],
    )
