"""资产管理应用的序列化器。"""

from rest_framework import serializers

from apps.asset import models
from apps.common.core.serializers import BaseModelSerializer, TabsColumn


class CloudServerSerializer(BaseModelSerializer):
    """云服务器资产序列化器。"""

    platform_info = serializers.SerializerMethodField(
        read_only=True,
        label='云平台',
        help_text='归属云平台的摘要信息',
    )

    def get_platform_info(self, obj: models.CloudServer) -> dict:
        """获取归属云平台的摘要信息。"""
        return {
            'pk': obj.platform.pk,
            'name': obj.platform.name,
            'platform_type': obj.platform.platform_type,
        }

    class Meta:
        """元数据配置。"""

        model = models.CloudServer
        tabs = [
            TabsColumn(
                '基本信息',
                [
                    'name',
                    'platform',
                    'instance_id',
                    'region',
                    'status',
                    'expire_time',
                    'is_active',
                    'company',
                    'description',
                ],
            ),
            TabsColumn(
                '配置信息',
                ['os_type', 'os_version', 'cpu', 'memory', 'disk_size'],
            ),
            TabsColumn(
                '网络信息',
                ['public_ip', 'private_ip'],
            ),
            TabsColumn(
                '标签扩展',
                ['tags'],
            ),
        ]
        fields = [
            'pk',
            'name',
            'platform',
            'platform_info',
            'instance_id',
            'public_ip',
            'private_ip',
            'os_type',
            'os_version',
            'cpu',
            'memory',
            'disk_size',
            'region',
            'status',
            'expire_time',
            'tags',
            'is_active',
            'company',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'name',
            'platform_info',
            'instance_id',
            'public_ip',
            'private_ip',
            'os_type',
            'cpu',
            'memory',
            'status',
            'expire_time',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': 'ID',
                'help_text': '主键唯一标识',
            },
            'name': {
                'label': '实例名称',
                'help_text': '云服务器实例名称，如 Web-Server-01',
            },
            'platform': {
                'attrs': ['pk', 'name', 'platform_type'],
                'required': True,
                'format': '{name}({platform_type})',
                'label': '归属云平台',
                'help_text': '该云服务器归属的云平台实例',
            },
            'instance_id': {
                'label': '实例 ID',
                'help_text': '云厂商分配的实例唯一标识，如 ins-xxxxx',
            },
            'public_ip': {
                'label': '公网 IP',
                'help_text': '公网 IPv4 地址',
            },
            'private_ip': {
                'label': '内网 IP',
                'help_text': '内网 / VPC 私有 IPv4 地址',
            },
            'os_type': {
                'label': '操作系统类型',
                'help_text': '服务器操作系统类型枚举',
            },
            'os_version': {
                'label': '操作系统版本',
                'help_text': '操作系统详细版本号',
            },
            'cpu': {
                'label': 'CPU 核数',
                'help_text': 'vCPU 核心数量',
            },
            'memory': {
                'label': '内存（GB）',
                'help_text': '内存大小，单位 GB',
            },
            'disk_size': {
                'label': '系统盘（GB）',
                'help_text': '系统盘容量，单位 GB',
            },
            'region': {
                'label': '区域',
                'help_text': '云厂商区域标识，如 ap-guangzhou',
            },
            'status': {
                'label': '运行状态',
                'help_text': '服务器当前运行状态',
            },
            'expire_time': {
                'label': '到期时间',
                'help_text': '实例到期时间，包年包月实例需关注',
            },
            'tags': {
                'label': '标签',
                'help_text': '云厂商标签键值对（JSON），用于分类筛选',
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
                'help_text': '资产归属的公司主体',
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


class DomainSerializer(BaseModelSerializer):
    """域名资产序列化器。"""

    platform_info = serializers.SerializerMethodField(
        read_only=True,
        label='云平台',
        help_text='归属云平台的摘要信息',
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
            'dns_server': {
                'label': 'DNS 服务器',
                'help_text': 'DNS 服务器列表，多个用逗号或换行分隔',
            },
            'status': {
                'label': '域名状态',
                'help_text': '域名当前状态',
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


class LocalServerSerializer(BaseModelSerializer):
    """本地物理服务器序列化器。"""

    class Meta:
        """元数据配置。"""

        model = models.LocalServer
        tabs = [
            TabsColumn(
                '基本信息',
                [
                    'name',
                    'hostname',
                    'ip_address',
                    'status',
                    'is_active',
                    'company',
                    'description',
                ],
            ),
            TabsColumn(
                'CPU 配置',
                ['cpu_count', 'cpu_model', 'cpu_total_cores', 'cpu_total_threads', 'cpu_detail'],
            ),
            TabsColumn(
                '内存配置',
                ['memory_count', 'memory_total', 'memory_type', 'memory_frequency', 'memory_detail'],
            ),
            TabsColumn(
                '硬盘配置',
                ['disk_count', 'disk_total', 'disk_detail'],
            ),
            TabsColumn(
                '系统与位置',
                [
                    'os_type',
                    'os_version',
                    'mac_address',
                    'rack_location',
                    'serial_number',
                    'purchase_date',
                    'warranty_expire',
                ],
            ),
        ]
        fields = [
            'pk',
            'name',
            'hostname',
            'ip_address',
            'mac_address',
            'os_type',
            'os_version',
            'cpu_count',
            'cpu_model',
            'cpu_total_cores',
            'cpu_total_threads',
            'cpu_detail',
            'memory_count',
            'memory_total',
            'memory_type',
            'memory_frequency',
            'memory_detail',
            'disk_count',
            'disk_total',
            'disk_detail',
            'rack_location',
            'serial_number',
            'purchase_date',
            'warranty_expire',
            'status',
            'is_active',
            'company',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'name',
            'hostname',
            'ip_address',
            'os_type',
            'cpu_count',
            'cpu_model',
            'cpu_total_cores',
            'memory_total',
            'disk_total',
            'rack_location',
            'status',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': 'ID',
                'help_text': '主键唯一标识',
            },
            'name': {
                'label': '主机名称',
                'help_text': '物理服务器显示名称，如 DC-Rack01-U10',
            },
            'hostname': {
                'label': '主机名',
                'help_text': '操作系统 hostname',
            },
            'ip_address': {
                'label': '管理 IP',
                'help_text': '主管理网口 IPv4 地址',
            },
            'mac_address': {
                'label': 'MAC 地址',
                'help_text': '管理网口 MAC 地址',
            },
            'os_type': {
                'label': '操作系统类型',
                'help_text': '服务器操作系统类型枚举',
            },
            'os_version': {
                'label': '操作系统版本',
                'help_text': '操作系统详细版本号',
            },
            # CPU 字段
            'cpu_count': {
                'label': 'CPU 数量',
                'help_text': '物理 CPU 颗数',
            },
            'cpu_model': {
                'label': 'CPU 型号',
                'help_text': 'CPU 型号，如 Intel Xeon Gold 6248R',
            },
            'cpu_total_cores': {
                'label': '总核心数',
                'help_text': '所有 CPU 物理核心总数',
            },
            'cpu_total_threads': {
                'label': '总线程数',
                'help_text': '所有 CPU 逻辑线程总数（含超线程）',
            },
            'cpu_detail': {
                'label': 'CPU 详细配置',
                'help_text': '每颗 CPU 的详细配置 JSON 列表，格式：[{"slot":1,"model":"Intel Xeon Gold 6248R","cores":24,"threads":48,"frequency":"3.0GHz"}]',
            },
            # 内存字段
            'memory_count': {
                'label': '内存条数量',
                'help_text': '物理内存条根数',
            },
            'memory_total': {
                'label': '内存总量（GB）',
                'help_text': '所有内存条合计容量，单位 GB',
            },
            'memory_type': {
                'label': '内存类型',
                'help_text': '内存类型，如 DDR4/DDR5',
            },
            'memory_frequency': {
                'label': '内存频率（MHz）',
                'help_text': '内存工作频率，如 3200',
            },
            'memory_detail': {
                'label': '内存详细配置',
                'help_text': '每条内存的详细配置 JSON 列表，格式：[{"slot":"DIMM_A1","capacity":32,"type":"DDR4","frequency":3200}]',
            },
            # 硬盘字段
            'disk_count': {
                'label': '硬盘数量',
                'help_text': '物理硬盘块数',
            },
            'disk_total': {
                'label': '磁盘总量（GB）',
                'help_text': '所有硬盘合计容量，单位 GB',
            },
            'disk_detail': {
                'label': '硬盘详细配置',
                'help_text': '每块硬盘的详细配置 JSON 列表，格式：[{"slot":"Slot0","capacity":960,"type":"SSD","interface":"SATA","model":"Intel S4510"}]',
            },
            # 位置与维保
            'rack_location': {
                'label': '机架位置',
                'help_text': '机房机架位置，如 DC-A-01-U10',
            },
            'serial_number': {
                'label': '序列号',
                'help_text': '硬件序列号（SN码）',
            },
            'purchase_date': {
                'label': '采购日期',
                'help_text': '硬件采购日期',
            },
            'warranty_expire': {
                'label': '维保到期',
                'help_text': '硬件维保到期日期',
            },
            'status': {
                'label': '运行状态',
                'help_text': '服务器当前运行状态',
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
                'help_text': '资产归属的公司主体',
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


class LocalVMSerializer(BaseModelSerializer):
    """本地虚拟主机序列化器。"""

    host_server_info = serializers.SerializerMethodField(
        read_only=True,
        label='宿主机',
        help_text='宿主物理服务器的摘要信息',
    )

    def get_host_server_info(self, obj: models.LocalVM) -> dict:
        """获取宿主机的摘要信息。"""
        return {
            'pk': obj.host_server.pk,
            'name': obj.host_server.name,
            'ip_address': obj.host_server.ip_address,
        }

    class Meta:
        """元数据配置。"""

        model = models.LocalVM
        tabs = [
            TabsColumn(
                '基本信息',
                [
                    'name',
                    'host_server',
                    'ip_address',
                    'hypervisor',
                    'vm_id',
                    'status',
                    'is_active',
                    'company',
                    'description',
                ],
            ),
            TabsColumn(
                '配置信息',
                ['os_type', 'os_version', 'cpu', 'memory', 'disk_size'],
            ),
            TabsColumn(
                '网络信息',
                ['mac_address'],
            ),
        ]
        fields = [
            'pk',
            'name',
            'host_server',
            'host_server_info',
            'ip_address',
            'mac_address',
            'os_type',
            'os_version',
            'cpu',
            'memory',
            'disk_size',
            'hypervisor',
            'vm_id',
            'status',
            'is_active',
            'company',
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'name',
            'host_server_info',
            'ip_address',
            'os_type',
            'cpu',
            'memory',
            'disk_size',
            'hypervisor',
            'status',
            'is_active',
            'created_time',
        ]
        extra_kwargs = {
            'pk': {
                'read_only': True,
                'label': 'ID',
                'help_text': '主键唯一标识',
            },
            'name': {
                'label': '虚拟机名称',
                'help_text': '虚拟机显示名称，如 K8s-Node-01',
            },
            'host_server': {
                'attrs': ['pk', 'name', 'ip_address'],
                'required': True,
                'format': '{name}({ip_address})',
                'label': '宿主机',
                'help_text': '运行该虚拟机的物理宿主机',
            },
            'ip_address': {
                'label': 'IP 地址',
                'help_text': '虚拟机 IPv4 地址',
            },
            'mac_address': {
                'label': 'MAC 地址',
                'help_text': '虚拟网卡 MAC 地址',
            },
            'os_type': {
                'label': '操作系统类型',
                'help_text': '虚拟机操作系统类型枚举',
            },
            'os_version': {
                'label': '操作系统版本',
                'help_text': '操作系统详细版本号',
            },
            'cpu': {
                'label': 'vCPU 核数',
                'help_text': '分配虚拟 CPU 核心数',
            },
            'memory': {
                'label': '内存（GB）',
                'help_text': '分配内存大小，单位 GB',
            },
            'disk_size': {
                'label': '磁盘容量（GB）',
                'help_text': '分配磁盘容量，单位 GB',
            },
            'hypervisor': {
                'label': '虚拟化平台',
                'help_text': '虚拟化平台类型枚举',
            },
            'vm_id': {
                'label': '虚拟机 ID',
                'help_text': '虚拟化平台内部虚拟机标识',
            },
            'status': {
                'label': '运行状态',
                'help_text': '虚拟机当前运行状态',
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
                'help_text': '资产归属的公司主体',
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
            'description',
            'created_time',
            'updated_time',
        ]
        table_fields = [
            'domain_info',
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
