<script lang="ts" setup>
import { ref, watch, nextTick, onBeforeUnmount } from "vue";
import { Graph, NodeEvent } from "@antv/g6";
import type { IPointerEvent } from "@antv/g6";
import { ElDrawer, ElButton, ElEmpty } from "element-plus";
import { fetchRelationGraph } from "@/api/asset";
import { http } from "@/utils/http";

const props = defineProps<{
  visible: boolean;
  domain: Record<string, any>;
}>();

const emit = defineEmits<{ (e: "update:visible", val: boolean): void }>();

const drawerVisible = ref(props.visible);
const graphContainer = ref<HTMLDivElement>();
const graphLoading = ref(false);
const graphEmpty = ref(false);
let graph: Graph | null = null;

// ---- 节点类型样式 ----
const TYPE_SHAPE: Record<string, string> = {
  domain: "circle",
  dns_record: "rect",
  cloud_server: "rect",
  local_server: "rect",
  local_vm: "rect",
  platform: "diamond",
  company: "triangle"
};

const TYPE_COLOR: Record<string, string> = {
  domain: "#3b82f6",
  dns_record: "#10b981",
  cloud_server: "#f59e0b",
  local_server: "#8b5cf6",
  local_vm: "#ec4899",
  platform: "#06b6d4",
  company: "#ef4444"
};

const TYPE_ZH: Record<string, string> = {
  domain: "域名",
  dns_record: "DNS",
  cloud_server: "云服务器",
  local_server: "物理机",
  local_vm: "虚拟机",
  platform: "云平台",
  company: "公司"
};

// ---- 详情面板 ----
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailType = ref("");
const detailFields = ref<{ label: string; value: string }[]>([]);

const FIELDS: Record<string, [string, string][]> = {
  domain: [
    ["域名", "domain_name"],
    ["注册商", "registrar"],
    ["DNS", "dns_server"],
    ["到期", "expire_time"]
  ],
  dns_record: [
    ["主机记录", "host"],
    ["类型", "record_type"],
    ["值", "value"],
    ["TTL", "ttl"]
  ],
  cloud_server: [
    ["名称", "name"],
    ["公网IP", "public_ip"],
    ["内网IP", "private_ip"],
    ["CPU", "cpu"],
    ["内存(GB)", "memory"]
  ],
  local_server: [
    ["名称", "name"],
    ["IP", "ip_address"],
    ["CPU线程", "cpu_total_threads"],
    ["内存", "memory_total"]
  ],
  local_vm: [
    ["名称", "name"],
    ["IP", "ip_address"],
    ["vCPU", "cpu"],
    ["内存(GB)", "memory"]
  ],
  platform: [
    ["名称", "name"],
    ["类型", "platform_type"],
    ["端点", "endpoint"]
  ],
  company: [
    ["名称", "name"],
    ["信用代码", "unified_social_credit_code"],
    ["法人", "legal_representative"]
  ]
};

const API: Record<string, string> = {
  domain: "/api/asset/domain/",
  dns_record: "/api/asset/dns-record/",
  cloud_server: "/api/asset/cloud-server/",
  local_server: "/api/asset/local-server/",
  local_vm: "/api/asset/local-vm/",
  platform: "/api/cloud/platform/",
  company: "/api/company/company/"
};

const openDetail = async (type: string, pk: string) => {
  detailType.value = type;
  detailVisible.value = true;
  detailLoading.value = true;
  detailFields.value = [];
  try {
    const base = API[type];
    if (base) {
      // 注意：后端 SimpleRouter(False) 不带尾部斜杠
      const res: any = await http.get(`${base}${pk}`);
      if (res?.code === 1000 && res?.data) {
        detailFields.value = (FIELDS[type] || []).map(([l, k]) => ({
          label: l,
          value: fmt(res.data[k])
        }));
        return;
      }
    }
  } catch {
    /* 无论成败都回退 */
  } finally {
    detailLoading.value = false;
  }
};

const fmt = (v: any): string => {
  if (v == null || v === "") return "-";
  if (typeof v === "object") return v.label || v.value || "-";
  return String(v);
};

// ---- 图谱 ----
const kill = () => {
  if (graph) {
    graph.destroy();
    graph = null;
  }
};

const loadGraph = async () => {
  if (!props.domain?.pk) return;
  kill();
  graphEmpty.value = false;
  graphLoading.value = true;
  try {
    const res: any = await fetchRelationGraph(props.domain.pk);
    const payload = res?.code === 1000 ? res.data : res;
    if (payload?.nodes?.length) {
      await nextTick();
      renderGraph(payload.nodes, payload.edges || []);
    } else {
      graphEmpty.value = true;
    }
  } catch {
    graphEmpty.value = true;
  } finally {
    graphLoading.value = false;
  }
};

const renderGraph = (nodes: any[], edges: any[]) => {
  kill();
  const el = graphContainer.value;
  if (!el) return;
  const w = el.clientWidth || 900;
  const h = el.clientHeight || 550;
  if (w === 0 || h === 0) {
    setTimeout(() => renderGraph(nodes, edges), 200);
    return;
  }

  const gNodes = nodes.map(n => ({
    id: n.id,
    data: {
      nodeType: n.type,
      label: n.label,
      typeZh: TYPE_ZH[n.type] || n.type,
      desc: buildDesc(n),
      raw: n
    }
  }));

  // force 布局自适应：DNS 越多，排斥力越小，更紧凑

  graph = new Graph({
    container: el,
    width: w,
    height: h,
    autoFit: "center",
    animation: true,
    background: "#fafbfc",
    data: {
      nodes: gNodes,
      edges: edges.map(e => ({
        source: e.source,
        target: e.target,
        data: { label: e.label || "" }
      }))
    },
    node: {
      type: (d: any) => TYPE_SHAPE[d.data.nodeType] || "rect",
      style(d: any): Record<string, unknown> {
        const t = d.data.nodeType;
        const shape = TYPE_SHAPE[t] || "rect";
        const base = baseNodeStyle(d);
        if (t === "dns_record") {
          const label = d.data.label || "";
          const w = Math.min(Math.max(label.length * 7 + 16, 56), 220);
          return { ...base, size: [w, 22], radius: 3 };
        }
        if (t === "domain") return { ...base, size: 62 };
        if (shape === "diamond" || shape === "triangle")
          return { ...base, size: 46 };
        const len = d.data.label?.length || 4;
        return {
          ...base,
          size: [Math.min(Math.max(len * 11 + 20, 70), 150), 32],
          radius: 6
        };
      },
      palette: {
        type: "group",
        field: (d: any) => d.data.nodeType,
        color: Object.values(TYPE_COLOR)
      },
      state: {
        hover: { fillOpacity: 0.25, lineWidth: 2.5, strokeOpacity: 1 }
      }
    },
    edge: {
      type: "polyline",
      style: {
        stroke: "#d0d5dd",
        strokeOpacity: 0.5,
        lineWidth: 1,
        endArrow: true,
        labelText: (d: any) => d.data?.label || "",
        labelFontSize: 9,
        labelFill: "#94a3b8",
        labelBackground: true,
        labelBackgroundFill: "#fff",
        labelBackgroundRadius: 3,
        labelBackgroundOpacity: 0.9,
        labelPadding: [1, 2],
        labelOffsetY: -2
      }
    },
    layout: {
      type: "dagre",
      rankdir: "LR",
      nodesep: 10,
      ranksep: 60
    },
    behaviors: ["drag-canvas", "zoom-canvas"],
    plugins: [
      {
        type: "tooltip",
        key: "node-tooltip",
        enable: (e: any) => e.targetType === "node",
        getContent: (_e: any, items: any[]) => {
          const d = items[0]?.data;
          if (!d) return "";
          const color = TYPE_COLOR[d.nodeType] || "#999";
          return `<div style="padding:6px 10px;font-size:12px;min-width:100px">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
              <span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0"></span>
              <b>${d.typeZh}：${d.label}</b>
            </div>
            ${d.desc ? `<div style="color:#888;font-size:11px">${d.desc}</div>` : ""}
          </div>`;
        }
      }
    ]
  });

  graph.on(NodeEvent.CLICK, (evt: IPointerEvent) => {
    const t = evt.target as { id?: string } | null;
    if (!t?.id || !graph) return;
    const nd = (graph.getNodeData(t.id) as any)?.data?.raw;
    if (nd?.pk && nd?.type) openDetail(nd.type, nd.pk);
  });

  graph.render();
};

/** 节点公共样式 */
const baseNodeStyle = (d: any) => ({
  fill: TYPE_COLOR[d.data.nodeType] || "#999",
  fillOpacity: 0.12,
  stroke: TYPE_COLOR[d.data.nodeType] || "#999",
  strokeOpacity: 0.5,
  lineWidth: 1.5,
  labelText: d.data.label,
  labelFill: "#334155",
  labelFontSize: d.data.nodeType === "dns_record" ? 10 : 12,
  labelPlacement: "center",
  labelWordWrap: false,
  labelMaxWidth: 200,
  labelPadding: d.data.nodeType === "dns_record" ? [1, 4] : [2, 6]
});

/** 根据节点类型生成简短描述 */
const buildDesc = (n: any) => {
  const t = n.type;
  if (t === "dns_record") return `值：${n.value || ""}`;
  if (t === "cloud_server" || t === "local_server" || t === "local_vm")
    return `IP：${n.ip || ""}`;
  if (t === "platform") return n.platform_type || "";
  if (t === "company") return n.full_name || "";
  if (t === "domain") return n.registrar || "";
  return "";
};

// ---- 生命周期 ----
watch(
  () => props.visible,
  val => {
    drawerVisible.value = val;
    if (val) {
      detailVisible.value = false;
      setTimeout(loadGraph, 200);
    }
  }
);
watch(drawerVisible, val => {
  if (!val) emit("update:visible", false);
});
onBeforeUnmount(() => kill());
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="`资产关联图谱 - ${domain?.domain_name || ''}`"
    direction="rtl"
    size="85%"
    destroy-on-close
  >
    <div class="graph-layout">
      <div ref="graphContainer" class="graph-area">
        <div v-if="graphLoading" class="graph-load">加载图谱中...</div>
        <div v-else-if="graphEmpty" class="graph-empty">
          <el-empty description="未找到关联资产" :image-size="80" />
        </div>
      </div>

      <div v-if="detailVisible" class="detail-panel">
        <div class="detail-head">
          <div class="flex items-center gap-2">
            <span
              class="detail-dot"
              :style="{ background: TYPE_COLOR[detailType] || '#999' }"
            />
            <span class="text-sm font-semibold">{{
              TYPE_ZH[detailType] || "详情"
            }}</span>
          </div>
          <el-button link size="small" @click="detailVisible = false"
            >✕</el-button
          >
        </div>
        <div v-loading="detailLoading" class="detail-body">
          <div v-if="detailFields.length" class="space-y-2.5">
            <div v-for="f in detailFields" :key="f.label" class="field-row">
              <span class="field-label">{{ f.label }}</span>
              <span class="field-value">{{ f.value }}</span>
            </div>
          </div>
          <div v-else class="text-center text-gray-400 text-sm py-6">
            暂无详情
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.graph-layout {
  display: flex;
  height: calc(100vh - 120px);
}

.graph-area {
  position: relative;
  flex: 1;
  min-height: 450px;
  overflow: hidden;
  border-radius: 8px;
}

.graph-load,
.graph-empty {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: #999;
  background: #fafbfc;
}

.detail-panel {
  flex-shrink: 0;
  width: 270px;
  overflow-y: auto;
  background: #fff;
  border-left: 1px solid #e5e7eb;
}

.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid #f0f0f0;
}

.detail-dot {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.detail-body {
  padding: 12px 14px;
}

.field-row {
  display: flex;
  flex-direction: column;
}

.field-label {
  margin-bottom: 1px;
  font-size: 11px;
  color: #94a3b8;
}

.field-value {
  font-size: 13px;
  color: #334155;
  word-break: break-all;
}
</style>
