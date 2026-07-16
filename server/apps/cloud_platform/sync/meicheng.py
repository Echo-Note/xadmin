"""美橙互联同步器 — 域名/DNS记录/余额。

API 文档: https://open.cndns.com/
基地址: https://api.cndns.com
鉴权: GET 请求 + checksum = md5(username + md5(password) + otime + email)
"""

import hashlib
import json
import logging
import re
from datetime import UTC, date, datetime
from decimal import Decimal

import requests

from apps.cloud_platform.sync.base import BaseCloudSyncer
from apps.cloud_platform.sync.engine import register_syncer
from apps.cloud_platform.sync.schemas import (
    BalanceSyncData,
    DnsRecordSyncData,
    DomainSyncData,
)

logger = logging.getLogger(__name__)

CNDNS_API_BASE = 'https://api.cndns.com'
CNDNS_TIMEOUT = 30

# 从 HTML/JSONP 中提取 JSON
_JSON_RE = re.compile(r'\{.*\}', re.DOTALL)

# 域名状态映射
_STATUS_MAP: dict[str, str] = {
    'pass': 'active',
    'run': 'active',
    'registered': 'active',
    'pause': 'paused',
    'processing': 'pending',
    'waiting': 'pending',
    'transfering': 'pending',
    'renewal process': 'pending',
    'deleted': 'deleted',
    'expired': 'expired',
}


@register_syncer
class MeichengSyncer(BaseCloudSyncer):
    """美橙互联域名注册商同步器。"""

    PLATFORM_TYPE = 'meicheng'
    PLATFORM_NAMES = ['美橙', '美橙互联', 'meicheng', 'cndns']
    SUPPORTED_RESOURCES = {'domain', 'dns_record', 'balance'}

    def __init__(self, cloud_platform):  # noqa: ANN001, D107
        super().__init__(cloud_platform)
        self._domain_list_cache: list[str] | None = None

    # ---------- 鉴权 ----------

    def _build_auth_params(self) -> dict[str, str]:
        """构建 CNDNS GET 请求鉴权参数。

        checksum = md5(username + md5(password) + otime(17位) + email)
        """
        creds = self.credentials
        username = creds.get('username', '')
        password = creds.get('password', '')
        email = creds.get('email', '')

        now = datetime.now()
        otime = now.strftime('%Y%m%d%H%M%S') + f'{now.microsecond // 1000:03d}'

        pwd_md5 = hashlib.md5(password.encode()).hexdigest()
        raw = f'{username}{pwd_md5}{otime}{email}'
        checksum = hashlib.md5(raw.encode()).hexdigest()

        return {'username': username, 'otime': otime, 'checksum': checksum}

    # ---------- HTTP 请求 ----------

    def _get(self, endpoint: str, extra_params: dict | None = None) -> dict | None:
        """发起 GET 请求到 CNDNS API，解析 HTML/JSON/JSONP 响应。"""
        params = self._build_auth_params()
        if extra_params:
            params.update(extra_params)

        url = f'{CNDNS_API_BASE}{endpoint}'
        logger.info('CNDNS GET %s', endpoint)

        try:
            resp = requests.get(url, params=params, timeout=CNDNS_TIMEOUT)
            resp.raise_for_status()
            return self._parse_response(resp.text, endpoint)
        except requests.RequestException as e:
            logger.warning('CNDNS 请求失败 [%s]: %s', endpoint, e)
            return None

    @staticmethod
    def _parse_response(text: str, endpoint: str = '') -> dict | None:
        """解析 CNDNS 响应：纯JSON → JSONP(修复转义) → message数组提取。"""
        text = text.strip()
        if not text:
            return None

        # 1. 纯 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if '{' in text and '}' in text:
            inner = text[text.index('{') : text.rindex('}') + 1]
            # 修复 CNDNS 将 " 转义为 \" 的问题
            cleaned = inner.replace('\\"', '"').replace('\\\\', '\\')

            # 2. 修复后完整解析
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            # 3. 提取 status + message 数组（message 可能含坏数据，逐项解析）
            status_m = re.search(r'"status"\s*:\s*"([^"]+)"', cleaned)
            if not status_m:
                logger.warning('CNDNS [%s] 无法提取status', endpoint)
                return None

            status = status_m.group(1)

            # 用括号匹配提取 message 数组内容
            msg_start = cleaned.find('"message"')
            if msg_start < 0:
                return {'status': status, 'message': []}
            bracket_start = cleaned.find('[', msg_start)
            if bracket_start < 0:
                return {'status': status, 'message': []}

            depth = 0
            bracket_end = bracket_start
            for i in range(bracket_start, len(cleaned)):
                if cleaned[i] == '[':
                    depth += 1
                elif cleaned[i] == ']':
                    depth -= 1
                    if depth == 0:
                        bracket_end = i + 1
                        break
            msg_content = cleaned[bracket_start + 1 : bracket_end - 1]  # 去掉外层 []

            # 逐项解析 domain 对象
            items = MeichengSyncer._parse_json_array(msg_content)
            return {'status': status, 'message': items}

        logger.warning('CNDNS [%s] 无法解析响应: %.200s', endpoint, text)
        return None

    @staticmethod
    def _parse_json_array(raw: str) -> list[dict]:
        """容错解析 JSON 数组字符串，逐项处理容错。

        当完整 JSON 解析失败时，按 },\\s*{ 分割后逐项 json.loads。
        单条解析失败跳过，不阻断整个列表。
        """
        # 先尝试整体解析
        try:
            return json.loads(f'[{raw}]')
        except json.JSONDecodeError:
            pass

        # 按 },{ 分割，逐项解析
        results: list[dict] = []
        depth = 0
        start = 0
        for i, ch in enumerate(raw):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    item_str = raw[start : i + 1]
                    try:
                        results.append(json.loads(item_str))
                    except json.JSONDecodeError:
                        logger.debug('CNDNS 跳过单条坏数据: %.100s', item_str)
                    start = i + 1
                    # 跳过逗号和空白
                    while start < len(raw) and raw[start] in ',\\s':
                        start += 1
        return results

    # ---------- 域名同步 ----------

    def _fetch_domain_list(self) -> list[str]:
        """获取域名列表（带缓存）。"""
        if self._domain_list_cache is not None:
            return self._domain_list_cache

        data = self._get('/domains/DomainList.aspx', {'domaintype': 'en'})
        if not data:
            self._domain_list_cache = []
            return []

        if data.get('status') != 'success':
            msg = data.get('message', 'unknown')
            logger.warning('美橙域名列表API返回失败: %s', msg)
            self._domain_list_cache = []
            return []

        items = data.get('message', [])
        names = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get('d_dme'):
                    names.append(str(item['d_dme']).strip().lower())
                elif isinstance(item, str) and item.strip():
                    names.append(item.strip().lower())
        self._domain_list_cache = names
        logger.info('美橙域名列表: %d 个', len(names))
        return names

    def _fetch_domains(self) -> list[DomainSyncData]:
        """从美橙 API DomainList.aspx 拉取完整域名信息。

        DomainList.aspx 一次返回所有域名的完整信息（含主体、日期、DNS等）。
        """
        data = self._get('/domains/DomainList.aspx', {'domaintype': 'en'})
        if not data:
            return []

        if data.get('status') != 'success':
            logger.warning('美橙域名列表API返回失败: %s', data.get('message', ''))
            return []

        items = data.get('message', [])
        if not isinstance(items, list):
            return []

        domains = []
        for item in items:
            if not isinstance(item, dict):
                continue
            dm = self._parse_domain_item(item)
            if dm:
                domains.append(dm)

        logger.info('美橙域名解析完成: %d 个', len(domains))
        return domains

    def _parse_domain_item(self, item: dict) -> DomainSyncData | None:
        """解析 DomainList.aspx 单条域名信息。

        关键字段: d_dme(域名), d_addtme(注册时间), d_exptme(到期时间),
        d_dnshst1~6(DNS), dom_org_cn(企业名), d_dnumber(信用代码),
        d_cattype(O/I), dom_fn_cn/dom_ln_cn(联系人), g_nme(产品名)
        """
        name = str(item.get('d_dme', '')).strip().lower()
        if not name:
            return None

        # 日期解析: YYYY/MM/DD HH:mm:ss
        def _parse_date(val) -> date | None:  # noqa: ANN001
            if not val:
                return None
            try:
                return datetime.strptime(str(val), '%Y/%m/%d %H:%M:%S').date()
            except (ValueError, TypeError):
                try:
                    return datetime.strptime(str(val), '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    return None

        # DNS
        dns_list = []
        for i in range(1, 7):
            ns = item.get(f'd_dnshst{i}')
            if ns:
                dns_list.append(str(ns))

        # 状态
        raw_state = str(item.get('d_dnvcstate', ''))
        status = _STATUS_MAP.get(raw_state, raw_state) or 'active'

        # 主体信息
        company_name = str(item.get('dom_org_cn', '')).strip() or None
        credit_code = str(item.get('d_dnumber', '')).strip() or None
        cat_type = str(item.get('d_cattype', '')).strip().upper()
        company_type = '企业' if cat_type == 'O' else ('个人' if cat_type == 'I' else None)
        family = str(item.get('dom_fn_cn', '')).strip()
        given = str(item.get('dom_ln_cn', '')).strip()
        legal_person = f'{family}{given}' if family or given else None
        phone = str(item.get('dom_ph', '')).strip().replace('.', '') or None
        email = str(item.get('dom_em', '')).strip() or None

        # 地址
        addr_parts = []
        for f in ('dom_st_cn', 'dom_ct_cn', 'dom_adr1_cn'):
            v = str(item.get(f, '')).strip()
            if v:
                addr_parts.append(v)
        address = ' '.join(addr_parts) if addr_parts else None

        return DomainSyncData(
            name=name,
            registrar_name='美橙',
            register_date=_parse_date(item.get('d_addtme')),
            expire_date=_parse_date(item.get('d_exptme')),
            dns_provider=', '.join(dns_list[:2]) if dns_list else '',
            status=status,
            owner_name=legal_person or company_name or '',
            company_name=company_name,
            credit_code=credit_code,
            company_type=company_type,
            legal_person=legal_person,
            address=address,
            contact_person=legal_person,
            contact_phone=phone,
            contact_email=email,
        )

    # ---------- DNS 解析记录 ----------

    def _is_platform_dns(self, domain) -> bool:  # noqa: ANN001
        """判断域名 DNS 是否由美橙管理。

        美橙 DNS：a.ezdnscenter.com / b.ezdnscenter.com

        Args:
            domain: Domain 模型实例。

        Returns:
            True 表示 DNS 托管在美橙。
        """
        dns = (domain.dns_server or '').lower()
        return 'ezdnscenter' in dns

    def _fetch_dns_records(self) -> list[DnsRecordSyncData]:
        """逐域名拉取 DNS 解析记录: /domains/RecList.aspx?domainname=xxx"""
        names = self._fetch_domain_list()
        if not names:
            return []

        all_records = []
        for name in names:
            data = self._get('/domains/RecList.aspx', {'domainname': name})
            if not data:
                continue
            if data.get('status') != 'success':
                continue

            records = data.get('message', [])
            if isinstance(records, list):
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    all_records.append(
                        DnsRecordSyncData(
                            domain_name=name,
                            record_type=str(rec.get('rec_type', 'A')),
                            host_record=str(rec.get('rec_item', '@')),
                            record_value=str(rec.get('rec_value', '')),
                            ttl=int(rec['rec_ttl']) if rec.get('rec_ttl') else 600,
                            line=str(rec.get('rec_line', '默认')),
                        )
                    )

        logger.info('美橙DNS解析记录: %d 条', len(all_records))
        return all_records

    # ---------- 余额 ----------

    def _fetch_balance(self) -> BalanceSyncData | None:
        """查询账户余额: /user/userdetail.aspx

        返回字段: availablebalance / balancemoney / frozenmoney / rewardmoney
        """
        data = self._get('/user/userdetail.aspx')
        if not data:
            return None
        if data.get('status') != 'success':
            logger.warning('美橙余额查询失败: %s', data.get('message', ''))
            return None

        info = data.get('message', {})
        if isinstance(info, list) and info:
            info = info[0]
        if not isinstance(info, dict):
            return None

        try:
            available = Decimal(str(info.get('availablebalance', '0')))
            balance = Decimal(str(info.get('balancemoney', '0')))
            frozen = Decimal(str(info.get('frozenmoney', '0')))
            reward = Decimal(str(info.get('rewardmoney', '0')))
            total = available + reward if reward > 0 else available

            return BalanceSyncData(
                total_balance=max(total, Decimal('0')),
                cash_balance=balance if balance > 0 else None,
                frozen_amount=abs(frozen) if frozen != 0 else None,
                currency='CNY',
                recorded_at=datetime.now(UTC),
            )
        except Exception as e:
            logger.warning('解析美橙余额失败: %s', e)
            return None
