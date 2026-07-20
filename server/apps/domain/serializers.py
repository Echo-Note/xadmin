"""域名管理应用的序列化器。

从 apps.asset.serializers 迁移而来，仅保留域名相关序列化器：
DomainSerializer / FilingSerializer / SslCertificateSerializer / DnsRecordSerializer。
"""

from rest_framework import serializers

from apps.common.core.serializers import BaseModelSerializer, TabsColumn
from apps.domain import models

# 备案状态 → el-tag 颜色类型（ICP/公安共用 IcpFilingStatusChoices）
_FILING_STATUS_TAG_TYPES: dict[str, str] = {
    'not_filed': 'danger',
    'filed': 'success',
    'pending_confirm': 'warning',
    'changing': 'info',
}

# ICP 预检测状态 → el-tag 颜色类型
_CHECK_STATUS_TAG_TYPES: dict[str, str] = {
    'not_checked': 'info',
    'passed': 'success',
    'suspected_missing': 'warning',
    'no_www_record': 'info',
    'check_failed': 'danger',
}

# 域名状态 → el-tag 颜色类型
_DOMAIN_STATUS_TAG_TYPES: dict[str, str] = {
    'active': 'success',
    'expired': 'danger',
    'pending': 'warning',
    'transferring': 'warning',
    'locked': 'danger',
    'forbidden': 'danger',
    'unverified': 'warning',
    'other': 'info',
}


class DomainSerializer(BaseModelSerializer):
    """域名资产序列化器。"""

    platform_info = serializers.SerializerMethodField(
        read_only=True,
        label='云平台',
        help_text='归属云平台的摘要信息',
    )
    dns_count = serializers.IntegerField(
        read_only=True,
        default=0,
        label='解析数量',
        help_text='该域名下的 DNS 解析记录数量',
    )
    filing_info = serializers.SerializerMethodField(
        read_only=True,
        label='备案信息',
        help_text='ICP 备案和公安备案的摘要信息',
    )

    def get_platform_info(self, obj: models.Domain) -> dict | None:
        """获取归属云平台的摘要信息。"""
        if obj.platform:
            return {
                'pk': obj.platform.pk,
                'name': obj.platform.name,
                'platform_type': obj.platform.platform_type,
            }
        return None

    def get_filing_info(self, obj: models.Domain) -> dict | None:
        """获取备案摘要信息（ICP + 公安）。"""
        try:
            f = obj.filing
            return {
                'pk': f.pk,
                'icp_number': f.icp_number,
                'icp_status': f.icp_status,
                'icp_check_status': f.icp_check_status,
                'ps_filing_number': f.ps_filing_number,
                'ps_status': f.ps_status,
            }
        except models.Filing.DoesNotExist:
            return None

    class Meta:
        """元数据配置。"""

        model = models.Domain
        tabs = [
            TabsColumn(
                '基本信息',
                [
                    'domain_name',
                    'registrar',
                    'platform',
                    'owner_name',
                    'status',
                    'is_active',
                    'company',
                    'description',
                ],
            ),
            TabsColumn(
                '时间信息',
                ['registration_time', 'expire_time'],
            ),
            TabsColumn(
                'DNS & SSL',
                ['dns_server', 'is_ssl_enabled', 'ssl_expire_time'],
            ),
            TabsColumn(
                '证书与责任人',
                [
                    'domain_certificate',
                    'security_contact',
                    'security_contact_phone',
                    'service_contact',
                    'service_contact_phone',
                ],
            ),
            TabsColumn(
                '备案信息',
                ['filing_info'],
            ),
        ]
        fields = [
            'pk',
            'domain_name',
            'registrar',
            'platform',
            'platform_info',
            'registration_time',
            'expire_time',
            'dns_server',
            'status',
            'owner_name',
            'is_ssl_enabled',
            'ssl_expire_time',
            'dns_count',
            'domain_certificate',
            'security_contact',
            'security_contact_phone',
            'service_contact',
            'service_contact_phone',
            'filing_info',
            'is_active',
            'company',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'domain_name',
            'registrar',
            'platform_info',
            'dns_count',
            'registration_time',
            'expire_time',
            'status',
            'is_ssl_enabled',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': 'ID',
                'help_text': '主键唯一标识',
            },
            'domain_name': {
                'label': '域名',
                'help_text': '完整域名，如 example.com，唯一',
            },
            'registrar': {
                'label': '注册商',
                'help_text': '域名注册服务商，如 腾讯云/阿里云/GoDaddy',
            },
            'platform': {
                'attrs': ['pk', 'name', 'platform_type'],
                'required': False,
                'format': '{name}({platform_type})',
                'label': '归属云平台',
                'help_text': '域名解析所在的云平台（可选）',
            },
            'registration_time': {
                'label': '注册时间',
                'help_text': '域名首次注册日期',
            },
            'expire_time': {
                'label': '到期时间',
                'help_text': '域名到期日期',
            },
            'dns_count': {
                'label': '解析数量',
                'help_text': '该域名下的 DNS 解析记录数量',
            },
            'dns_server': {
                'label': 'DNS 服务器',
                'help_text': 'DNS 服务器列表，多个用逗号或换行分隔',
            },
            'status': {
                'label': '域名状态',
                'help_text': '域名当前状态',
                'tag_types': _DOMAIN_STATUS_TAG_TYPES,
            },
            'owner_name': {
                'label': '所有者',
                'help_text': '域名所有者/联系人姓名',
            },
            'is_ssl_enabled': {
                'label': 'SSL 证书',
                'help_text': '是否已部署 SSL 证书',
            },
            'ssl_expire_time': {
                'label': 'SSL 到期时间',
                'help_text': 'SSL 证书到期日期',
            },
            'domain_certificate': {
                'label': '域名证书',
                'help_text': '域名注册证书/实名认证证书扫描件上传',
            },
            'security_contact': {
                'label': '安全责任人',
                'help_text': '域名安全责任人姓名',
            },
            'security_contact_phone': {
                'label': '安全责任人电话',
                'help_text': '安全责任人联系电话',
            },
            'service_contact': {
                'label': '服务负责人',
                'help_text': '域名服务/运维负责人姓名',
            },
            'service_contact_phone': {
                'label': '服务负责人电话',
                'help_text': '服务负责人联系电话',
            },
            'is_active': {
                'label': '启用状态',
                'help_text': '是否纳入资产管理范围',
            },
            'company': {
                'attrs': ['pk', 'name', 'short_name'],
                'required': False,
                'format': '{name}',
                'label': '所属公司',
                'help_text': '域名归属的公司主体',
            },
            'description': {
                'label': 'Description',
                'help_text': '备注信息',
            },
            'created_time': {
                'read_only': True,
                'label': 'Created time',
                'help_text': '创建时间',
            },
            'updated_time': {
                'read_only': True,
                'label': 'Updated time',
                'help_text': '更新时间',
            },
        }


class SslCertificateSerializer(BaseModelSerializer):
    """SSL 证书详细信息序列化器。"""

    domains_info = serializers.SerializerMethodField(
        read_only=True,
        label='关联域名',
        help_text='使用该证书的所有域名列表',
    )

    def get_domains_info(self, obj: models.SslCertificate) -> str:
        """获取使用该证书的所有域名，逗号分隔。"""
        return ', '.join(d.domain_name for d in obj.domains.all())

    class Meta:
        """元数据配置。"""

        model = models.SslCertificate
        tabs = [
            TabsColumn(
                '基本信息',
                ['domains_info', 'is_valid', 'check_time'],
            ),
            TabsColumn(
                '主体信息',
                ['subject_cn', 'subject_o', 'subject_ou'],
            ),
            TabsColumn(
                '颁发者信息',
                ['issuer_cn', 'issuer_o'],
            ),
            TabsColumn(
                '证书属性',
                [
                    'serial_number',
                    'signature_algorithm',
                    'not_before',
                    'not_after',
                    'san_domains',
                ],
            ),
            TabsColumn(
                '证书文件',
                ['certificate_pem', 'intermediate_pem', 'private_key_pem'],
            ),
        ]
        fields = [
            'pk',
            'fingerprint',
            'domains_info',
            'subject_cn',
            'subject_o',
            'subject_ou',
            'issuer_cn',
            'issuer_o',
            'serial_number',
            'signature_algorithm',
            'not_before',
            'not_after',
            'san_domains',
            'is_valid',
            'check_time',
            'certificate_pem',
            'intermediate_pem',
            'private_key_pem',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'domains_info',
            'subject_cn',
            'issuer_cn',
            'not_after',
            'is_valid',
            'san_domains',
            'check_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': 'ID',
                'help_text': '主键唯一标识',
            },
            'fingerprint': {
                'read_only': True,
                'label': '证书指纹',
                'help_text': 'SHA256 指纹，用于判断证书是否完全一致',
            },
            'subject_cn': {
                'label': '主体通用名',
                'help_text': '证书主体 Common Name',
            },
            'subject_o': {
                'label': '主体组织',
                'help_text': '证书主体 Organization',
            },
            'subject_ou': {
                'label': '主体组织单元',
                'help_text': '证书主体 Organizational Unit',
            },
            'issuer_cn': {
                'label': '颁发机构通用名',
                'help_text': '颁发机构 Common Name',
            },
            'issuer_o': {
                'label': '颁发机构组织',
                'help_text': '颁发机构 Organization',
            },
            'serial_number': {
                'label': '序列号',
                'help_text': '证书唯一序列号（十六进制）',
            },
            'signature_algorithm': {
                'label': '签名算法',
                'help_text': '证书签名哈希算法',
            },
            'not_before': {
                'label': '有效期起始',
                'help_text': '证书生效时间（UTC）',
            },
            'not_after': {
                'label': '有效期结束',
                'help_text': '证书到期时间（UTC）',
            },
            'san_domains': {
                'label': '备用域名',
                'help_text': 'Subject Alternative Names 域名列表',
            },
            'certificate_pem': {
                'label': '终端证书',
                'help_text': '终端证书 PEM 格式内容（自动检测填充）',
            },
            'intermediate_pem': {
                'label': '中间证书',
                'help_text': '中间证书链 PEM 格式内容（自动检测填充）',
            },
            'private_key_pem': {
                'label': '私钥',
                'help_text': '私钥 PEM 格式内容（加密存储，需手动上传）',
            },
            'is_valid': {
                'label': '是否有效',
                'help_text': '检测时证书是否在有效期内',
            },
            'check_time': {
                'label': '检测时间',
                'help_text': '最近一次 SSL 证书检测时间',
            },
            'description': {
                'label': 'Description',
                'help_text': '备注信息',
            },
            'created_time': {
                'read_only': True,
                'label': 'Created time',
                'help_text': '创建时间',
            },
            'updated_time': {
                'read_only': True,
                'label': 'Updated time',
                'help_text': '更新时间',
            },
        }


class DnsRecordSerializer(BaseModelSerializer):
    """DNS 解析记录序列化器。"""

    domain_info = serializers.SerializerMethodField(
        read_only=True,
        label='所属域名',
        help_text='归属域名的摘要信息',
    )

    def get_domain_info(self, obj: models.DnsRecord) -> dict:
        """获取归属域名的摘要信息。"""
        return {
            'pk': obj.domain.pk,
            'domain_name': obj.domain.domain_name,
        }

    class Meta:
        """元数据配置。"""

        model = models.DnsRecord
        fields = [
            'pk',
            'domain',
            'domain_info',
            'record_type',
            'host',
            'value',
            'ttl',
            'priority',
            'is_active',
            'is_ssl_enabled',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'domain',
            'record_type',
            'host',
            'value',
            'ttl',
            'priority',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {'read_only': True, 'label': 'ID', 'help_text': '主键唯一标识'},
            'domain': {
                'attrs': ['pk', 'domain_name'],
                'required': True,
                'format': '{domain_name}',
                'label': '所属域名',
                'help_text': '该解析记录归属的域名',
            },
            'record_type': {
                'label': '记录类型',
                'help_text': 'DNS 记录类型：A/AAAA/CNAME/MX/TXT/NS/SRV/CAA',
            },
            'host': {
                'label': '主机记录',
                'help_text': '主机记录前缀，如 @、www、mail',
            },
            'value': {
                'label': '记录值',
                'help_text': '解析目标，A记录为IP、CNAME为目标域名等',
            },
            'ttl': {'label': 'TTL（秒）', 'help_text': '生存时间，默认 600 秒'},
            'priority': {
                'label': '优先级',
                'help_text': 'MX/SRV 记录的优先级，值越小优先级越高',
            },
            'is_active': {'label': '启用状态', 'help_text': '解析记录是否生效'},
            'is_ssl_enabled': {'label': 'SSL 证书', 'help_text': '该子域名是否支持 HTTPS'},
            'description': {'label': 'Description', 'help_text': '备注信息'},
            'created_time': {
                'read_only': True,
                'label': 'Created time',
                'help_text': '创建时间',
            },
            'updated_time': {
                'read_only': True,
                'label': 'Updated time',
                'help_text': '更新时间',
            },
        }


class FilingSerializer(BaseModelSerializer):
    """备案信息序列化器，同时管理 ICP 备案与公安备案。"""

    domain_info = serializers.SerializerMethodField(
        read_only=True,
        label='关联域名',
        help_text='归属域名的摘要信息',
    )

    def get_domain_info(self, obj: models.Filing) -> dict:
        """获取归属域名的摘要信息。

        由 Domain 主域名与 DnsRecord 表中**实际存在的 www 记录**拼接生成关联域名：
        存在 host='www' 的解析记录时，关联域名为 www.{主域名}；
        否则关联域名为主域名本身。返回完整域名（label）与 https 访问地址（url）。

        依赖 ViewSet 通过 Prefetch 预加载的 www_dns_records 属性，避免 N+1 查询。
        """
        domain = obj.domain
        base = domain.domain_name
        has_www = bool(getattr(domain, 'www_dns_records', None))
        full = f'www.{base}' if has_www else base
        return {'pk': domain.pk, 'label': full, 'url': f'https://{full}'}

    class Meta:
        """元数据配置。"""

        model = models.Filing
        tabs = [
            TabsColumn(
                '基本信息',
                ['domain', 'company'],
            ),
            TabsColumn(
                'ICP 备案',
                [
                    'icp_number',
                    'icp_filing_date',
                    'icp_unit_name',
                    'icp_status',
                    'icp_check_status',
                    'icp_has_www_record',
                    'icp_footer_content',
                    'icp_check_conclusion',
                    'icp_check_time',
                ],
            ),
            TabsColumn(
                '公安备案',
                [
                    'ps_filing_number',
                    'ps_filing_date',
                    'ps_unit_name',
                    'ps_public_security_agency',
                    'ps_status',
                ],
            ),
        ]
        fields = [
            'pk',
            'domain',
            'domain_info',
            'company',
            # ICP
            'icp_number',
            'icp_filing_date',
            'icp_unit_name',
            'icp_status',
            'icp_check_status',
            'icp_has_www_record',
            'icp_footer_content',
            'icp_check_conclusion',
            'icp_check_time',
            # 公安
            'ps_filing_number',
            'ps_filing_date',
            'ps_unit_name',
            'ps_public_security_agency',
            'ps_status',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'domain_info',
            'icp_number',
            'icp_status',
            'icp_check_status',
            'ps_filing_number',
            'ps_status',
            'company',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': 'ID',
                'help_text': '主键唯一标识',
            },
            'domain': {
                'attrs': ['pk', 'domain_name'],
                'required': True,
                'format': '{domain_name}',
                'label': '关联域名',
                'help_text': '该备案记录关联的域名',
            },
            'company': {
                'attrs': ['pk', 'name', 'short_name'],
                'required': False,
                'format': '{name}',
                'label': '所属公司',
                'help_text': '备案主体归属的公司',
            },
            # ICP 字段
            'icp_number': {
                'label': 'ICP 备案号',
                'help_text': 'ICP 备案号，如 京ICP备2023000001号',
            },
            'icp_filing_date': {
                'label': 'ICP 备案日期',
                'help_text': 'ICP 备案通过日期',
            },
            'icp_unit_name': {
                'label': 'ICP 备案主体',
                'help_text': 'ICP 备案主体名称（单位/个人名称）',
            },
            'icp_status': {
                'label': 'ICP 备案状态',
                'help_text': 'ICP 备案当前状态：未备案/已备案/待人工确认/变更中',
                'tag_types': _FILING_STATUS_TAG_TYPES,
            },
            'icp_check_status': {
                'label': 'ICP 预检测状态',
                'help_text': '首页悬挂备案号预检测结果',
                'tag_types': _CHECK_STATUS_TAG_TYPES,
            },
            'icp_has_www_record': {
                'label': '有www解析',
                'help_text': '域名是否存在 www 子域名的 DNS 解析记录',
            },
            'icp_footer_content': {
                'label': '页脚内容',
                'help_text': '首页页脚区域抓取到的文本内容',
            },
            'icp_check_conclusion': {
                'label': '检测结论',
                'help_text': '预检测的详细结论描述',
            },
            'icp_check_time': {
                'read_only': True,
                'label': '检测时间',
                'help_text': '最近一次预检测执行时间',
            },
            # 公安字段
            'ps_filing_number': {
                'label': '公安备案号',
                'help_text': '公安联网备案号，如 京公网安备110100000001号',
            },
            'ps_filing_date': {
                'label': '公安备案日期',
                'help_text': '公安联网备案通过日期',
            },
            'ps_unit_name': {
                'label': '公安备案主体',
                'help_text': '公安备案主体名称',
            },
            'ps_public_security_agency': {
                'label': '备案公安机关',
                'help_text': '受理备案的公安机关名称',
            },
            'ps_status': {
                'label': '公安备案状态',
                'help_text': '公安备案当前状态：未备案/已备案/待人工确认',
                'tag_types': _FILING_STATUS_TAG_TYPES,
            },
            'description': {
                'label': 'Description',
                'help_text': '备注信息',
            },
            'created_time': {
                'read_only': True,
                'label': 'Created time',
                'help_text': '创建时间',
            },
            'updated_time': {
                'read_only': True,
                'label': 'Updated time',
                'help_text': '更新时间',
            },
        }
