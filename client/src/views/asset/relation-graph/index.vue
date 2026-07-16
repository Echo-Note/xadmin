<script lang="ts" setup>
import {
  ref,
  shallowRef,
  onMounted,
  onBeforeUnmount,
  nextTick,
  watch
} from "vue";
import { Graph, NodeEvent, CanvasEvent } from "@antv/g6";
import type { IPointerEvent } from "@antv/g6";
import { ElMessage, ElSelect, ElOption, ElButton } from "element-plus";
import { domainApi, fetchRelationGraph } from "@/api/asset";
import { http } from "@/utils/http";

defineOptions({ name: "AssetRelationGraph" });

// ---- 域名选择 ----
const domainLoading = ref(false);
const domainList = ref<{ pk: string; domain_name: string }[]>([]);
const selectedDomain = ref("");

const loadDomains = async () => {
  domainLoading.value = true;
  try {
    const res: any = await domainApi.list({ page: 1, size: 1000 });
    if (res.code === 1000) {
      domainList.value = res.data.results || [];
    }
  } finally {
    domainLoading.value = false;
  }
};

const handleSearch = async () => {
  if (!selectedDomain.value) {
    ElMessage.warning("请先选择一个域名");
    return;
  }
  await loadGraph();
};

// ---- G6 图谱 ----
const graphContainer = ref<HTMLDivElement>();
let graph: Graph | null = null;
const graphLoading = ref(false);

// 节点类型映射：类型 → 颜色、形状
const NODE_STYLE: Record<
  string,
  { fill: string; stroke: string; icon: string }
> = {
  domain: { fill: "#e8f4fd", stroke: "#409eff", icon: "🌐" },
  dns_record: { fill: "#ecf5e4", stroke: "#67c23a", icon: "📋" },
  cloud_server: { fill: "#fef0e6", stroke: "#e6a23c", icon: "☁️" },
  local_server: { fill: "#f4e8fc", stroke: "#a855f7", icon: "🖥️" },
  local_vm: { fill: "#fde8ef", stroke: "#ec4899", icon: "💻" },
  platform: { fill: "#e0f2fe", stroke: "#06b6d4", icon: "🏢" },
  company: { fill: "#fee2e2", stroke: "#ef4444", icon: "🏛️" }
};

// 图表数据缓存
const graphData = ref<{ nodes: any[]; edges: any[] } | null>(null);

const loadGraph = async () => {
  if (!selectedDomain.value) return;
  graphLoading.value = true;
  try {
    const res = await fetchRelationGraph(selectedDomain.value);
    if ((res as any).code === 1000) {
      graphData.value = (res as any).data;
      renderGraph((res as any).data);
    }
  } catch {
    ElMessage.error("加载图谱数据失败");
  } finally {
    graphLoading.value = false;
  }
};

const renderGraph = (data: { nodes: any[]; edges: any[] }) => {
  if (!graphContainer.value) return;

  // 销毁旧图
  if (graph) {
    graph.destroy();
    graph = null;
  }

  const container = graphContainer.value;
  const width = container.clientWidth || 900;
  const height = container.clientHeight || 600;

  graph = new Graph({
    container,
    width,
    height,
    autoFit: "center",
    animation: true,
    data: {
      nodes: data.nodes.map((n: any) => formatNode(n)),
      edges: data.edges.map((e: any) => ({
        source: e.source,
        target: e.target,
        data: { label: e.label }
      }))
    },
    node: {
      type: "rect",
      style: {
        size: (d: any) => [Math.max(d.data.labelWidth || 120, 140), 52],
        radius: 10,
        fill: (d: any) => d.data.fill,
        stroke: (d: any) => d.data.stroke,
        lineWidth: 2,
        labelText: (d: any) => d.data.label,
        labelFill: "#333",
        labelFontSize: 13,
        labelPlacement: "center",
        labelWordWrap: true,
        labelMaxWidth: 130
      }
    },
    edge: {
      type: "polyline",
      style: {
        stroke: "#b0b0b0",
        lineWidth: 1.5,
        endArrow: true,
        labelText: (d: any) => d.data?.label || "",
        labelFontSize: 11,
        labelFill: "#888",
        labelBackground: true,
        labelBackgroundFill: "#fff",
        labelBackgroundRadius: 4,
        labelBackgroundOpacity: 0.9
      }
    },
    layout: {
      type: "dagre",
      rankdir: "LR",
      nodesep: 40,
      ranksep: 120
    },
    behaviors: ["drag-canvas", "zoom-canvas"]
  });

  // 节点点击 → 加载详情
  graph.on(NodeEvent.CLICK, (evt: IPointerEvent) => {
    const nodeId = evt.target.id;
    const nodeData = graph!.getNodeData(nodeId);
    const raw = nodeData?.data?.raw || {};
    if (raw.pk && raw.type) {
      openDetail(raw.type, raw.pk);
    }
  });

  // 画布空白点击 → 关闭面板
  graph.on(CanvasEvent.CLICK, () => {
    // 不使用，避免与节点点击冲突
  });

  graph.render();
};

/** 格式化后端节点为 G6 格式 */
const formatNode = (n: any) => {
  const style = NODE_STYLE[n.type] || NODE_STYLE.domain;
  const icon = style.icon;
  const raw = { pk: n.pk, type: n.type, label: n.label, ...n };
  // 双行标签：图标 + 名称
  const displayLabel = `${icon} ${n.label}`;

  return {
    id: n.id,
    data: {
      label: displayLabel,
      labelWidth: Math.max(n.label.length * 14, 100),
      fill: style.fill,
      stroke: style.stroke,
      raw
    }
  };
};

// ---- 详情面板 ----
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailType = ref("");
const detailData = ref<Record<string, any>>({});

const DETAIL_FIELDS: Record<string, { label: string; key: string }[]> = {
  domain: [
    { label: "域名", key: "domain_name" },
    { label: "注册商", key: "registrar" },
    { label: "DNS 服务器", key: "dns_server" },
    { label: "所有者", key: "owner_name" },
    { label: "到期时间", key: "expire_time" },
    { label: "SSL 证书", key: "is_ssl_enabled" }
  ],
  dns_record: [
    { label: "主机记录", key: "host" },
    { label: "记录类型", key: "record_type" },
    { label: "记录值", key: "value" },
    { label: "TTL", key: "ttl" },
    { label: "优先级", key: "priority" }
  ],
  cloud_server: [
    { label: "实例名称", key: "name" },
    { label: "实例 ID", key: "instance_id" },
    { label: "公网 IP", key: "public_ip" },
    { label: "内网 IP", key: "private_ip" },
    { label: "系统", key: "os_type" },
    { label: "CPU", key: "cpu" },
    { label: "内存(GB)", key: "memory" },
    { label: "状态", key: "status" }
  ],
  local_server: [
    { label: "主机名称", key: "name" },
    { label: "管理 IP", key: "ip_address" },
    { label: "系统", key: "os_type" },
    { label: "CPU", key: "cpu_total_threads" },
    { label: "内存(GB)", key: "memory_total" },
    { label: "状态", key: "status" }
  ],
  local_vm: [
    { label: "虚拟机名称", key: "name" },
    { label: "IP", key: "ip_address" },
    { label: "系统", key: "os_type" },
    { label: "vCPU", key: "cpu" },
    { label: "内存(GB)", key: "memory" },
    { label: "状态", key: "status" }
  ],
  platform: [
    { label: "平台名称", key: "name" },
    { label: "平台类型", key: "platform_type" },
    { label: "端点", key: "endpoint" }
  ],
  company: [
    { label: "公司名称", key: "name" },
    { label: "简称", key: "short_name" },
    { label: "信用代码", key: "unified_social_credit_code" },
    { label: "法定代表人", key: "legal_representative" }
  ]
};

/** 根据类型和 URL 映射，确定 API 路径 */
const getDetailUrl = (type: string): string => {
  const map: Record<string, string> = {
    domain: "/api/asset/domain/",
    dns_record: "/api/asset/dns-record/",
    cloud_server: "/api/asset/cloud-server/",
    local_server: "/api/asset/local-server/",
    local_vm: "/api/asset/local-vm/"
  };
  // platform 和 company 目前没有独立的详情 API，但仍可展示节点元数据
  return map[type] || "";
};

const openDetail = async (type: string, pk: string) => {
  detailType.value = type;
  detailVisible.value = true;
  detailLoading.value = true;
  detailData.value = {};

  try {
    const baseUrl = getDetailUrl(type);
    if (baseUrl) {
      const res: any = await http.get(`${baseUrl}${pk}/`);
      if (res.code === 1000) {
        detailData.value = res.data || {};
        return;
      }
    }
    // 回退：使用节点携带的元数据
    detailData.value = { name: pk, _no_detail: true };
  } catch {
    detailData.value = { name: pk, _no_detail: true };
  } finally {
    detailLoading.value = false;
  }
};

const fieldLabel = (val: any): string => {
  if (!val) return "-";
  if (typeof val === "object") return val.label || val.value || "-";
  return String(val);
};

// ---- 生命周期 ----
onMounted(() => {
  loadDomains();
});

onBeforeUnmount(() => {
  if (graph) {
    graph.destroy();
    graph = null;
  }
});

// 窗口大小变化时重绘
const handleResize = () => {
  if (graph && graphContainer.value) {
    const { clientWidth, clientHeight } = graphContainer.value;
    graph.setSize(clientWidth, clientHeight);
  }
};

// 自动选择第一个域名
watch(
  domainList,
  list => {
    if (list.length > 0 && !selectedDomain.value) {
      selectedDomain.value = list[0].pk;
      nextTick(() => loadGraph());
    }
  },
  { immediate: false }
);
</script>

<template>
  <div class="relation-graph-page h-[calc(100vh-120px)] flex flex-col">
    <!-- 顶部选择栏 -->
    <div
      class="flex items-center gap-3 px-6 py-3 bg-bg_color border-b border-[var(--el-border-color-lighter)]"
    >
      <span class="text-sm font-medium whitespace-nowrap">选择域名：</span>
      <el-select
        v-model="selectedDomain"
        filterable
        placeholder="请选择域名"
        :loading="domainLoading"
        class="w-80"
        @change="loadGraph"
      >
        <el-option
          v-for="d in domainList"
          :key="d.pk"
          :label="d.domain_name"
          :value="d.pk"
        />
      </el-select>
      <el-button type="primary" @click="handleSearch">查看图谱</el-button>
    </div>

    <!-- 主体区域 -->
    <div class="flex flex-1 overflow-hidden">
      <!-- 图谱画布 -->
      <div ref="graphContainer" class="flex-1 relative" @resize="handleResize">
        <div
          v-if="graphLoading"
          class="absolute inset-0 flex items-center justify-center bg-white/80 z-10"
        >
          <span class="text-sm text-gray-500">加载图谱中...</span>
        </div>
        <div
          v-if="!graphData && !graphLoading"
          class="absolute inset-0 flex items-center justify-center"
        >
          <span class="text-sm text-gray-400"
            >请选择一个域名查看资产关联图谱</span
          >
        </div>
      </div>

      <!-- 右侧详情面板 -->
      <transition name="slide-right">
        <div
          v-if="detailVisible"
          class="w-80 border-l border-[var(--el-border-color-lighter)] bg-bg_color overflow-y-auto flex-shrink-0"
        >
          <div
            class="flex items-center justify-between px-4 py-3 border-b border-[var(--el-border-color-lighter)]"
          >
            <span class="text-sm font-semibold">
              {{ NODE_STYLE[detailType]?.icon || "📄" }}
              {{
                detailType === "cloud_server"
                  ? "云服务器详情"
                  : detailType === "local_server"
                    ? "物理服务器详情"
                    : detailType === "local_vm"
                      ? "虚拟主机详情"
                      : detailType === "dns_record"
                        ? "DNS 记录详情"
                        : detailType === "platform"
                          ? "云平台详情"
                          : detailType === "company"
                            ? "公司详情"
                            : "域名详情"
              }}
            </span>
            <el-button
              link
              type="info"
              size="small"
              @click="detailVisible = false"
            >
              ✕
            </el-button>
          </div>

          <div v-loading="detailLoading" class="p-4">
            <template v-if="detailData._no_detail">
              <div class="text-sm text-gray-400 py-8 text-center">
                暂无详细信息
              </div>
            </template>
            <template v-else-if="DETAIL_FIELDS[detailType]">
              <div class="space-y-3">
                <div
                  v-for="f in DETAIL_FIELDS[detailType]"
                  :key="f.key"
                  class="flex flex-col"
                >
                  <span
                    class="text-xs text-[var(--el-text-color-secondary)] mb-0.5"
                  >
                    {{ f.label }}
                  </span>
                  <span class="text-sm">{{
                    fieldLabel(detailData[f.key])
                  }}</span>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="text-sm text-gray-400 py-8 text-center">
                不支持的资产类型
              </div>
            </template>
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
.relation-graph-page {
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.3s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  opacity: 0;
  transform: translateX(320px);
}
</style>
