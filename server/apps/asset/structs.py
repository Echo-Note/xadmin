"""资产应用的嵌入式 JSON 数据结构定义。

使用 Pydantic 模型定义 JSONField 中存储的数据结构，同时提供校验能力。
"""

from pydantic import BaseModel, Field


class CpuDetailItem(BaseModel):
    """单颗物理 CPU 的详细配置。"""

    slot: int = Field(ge=1, description='CPU 插槽编号，从 1 开始')
    model: str = Field(min_length=1, description='CPU 型号，如 Intel Xeon Gold 6248R')
    cores: int = Field(ge=1, description='物理核心数')
    threads: int = Field(ge=1, description='逻辑线程数（含超线程）')
    frequency: str = Field(min_length=1, description='主频，如 3.0GHz')


class MemoryDetailItem(BaseModel):
    """单条内存的详细配置。"""

    slot: str = Field(min_length=1, description='内存插槽标识，如 DIMM_A1')
    capacity: int = Field(ge=1, description='容量，单位 GB')
    type: str = Field(min_length=1, description='内存类型，如 DDR4、DDR5')
    frequency: int = Field(ge=1, description='工作频率，单位 MHz，如 3200')


class DiskDetailItem(BaseModel):
    """单块硬盘的详细配置。"""

    slot: str = Field(min_length=1, description='硬盘插槽标识，如 Slot0')
    capacity: int = Field(ge=1, description='容量，单位 GB')
    type: str = Field(min_length=1, description='硬盘类型：SSD、HDD、NVMe 等')
    interface: str = Field(min_length=1, description='接口类型：SATA、SAS、PCIe 等')
    model: str = Field(default='', description='硬盘型号，如 Intel S4510')
