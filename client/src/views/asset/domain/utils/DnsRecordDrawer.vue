<script lang="ts" setup>
import { ref, reactive, watch, computed } from "vue";
import {
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElMessageBox,
  ElMessage,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElSwitch,
  ElDescriptions,
  ElDescriptionsItem,
  ElEmpty
} from "element-plus";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { dnsRecordApi } from "@/api/asset";

/** DNS 记录类型枚举 */
const recordTypes = [
  { value: "A", label: "A" },
  { value: "AAAA", label: "AAAA" },
  { value: "CNAME", label: "CNAME" },
  { value: "MX", label: "MX" },
  { value: "TXT", label: "TXT" },
  { value: "NS", label: "NS" },
  { value: "SRV", label: "SRV" },
  { value: "CAA", label: "CAA" }
];

interface DnsRecordItem {
  pk: string;
  domain: string;
  record_type: string | { value: string; label: string };
  host: string;
  value: string;
  ttl: number;
  priority?: number;
  is_active: boolean;
}

const props = defineProps<{
  visible: boolean;
  domain: Record<string, any>;
}>();

const emit = defineEmits<{
  (e: "update:visible", val: boolean): void;
}>();

const drawerVisible = ref(props.visible);
const loading = ref(false);
const tableData = ref<DnsRecordItem[]>([]);

/** 表单状态 */
const formVisible = ref(false);
const formTitle = ref("新增解析记录");
const formLoading = ref(false);
const isEdit = ref(false);
const currentPk = ref("");

const formData = reactive({
  domain: "",
  record_type: "A",
  host: "@",
  value: "",
  ttl: 600,
  priority: undefined as number | undefined,
  is_active: true
});

/** 需要优先级的记录类型 */
const NEEDS_PRIORITY = ["MX", "SRV"];

/** 监听 visible 变化 */
watch(
  () => props.visible,
  val => {
    drawerVisible.value = val;
    if (val && props.domain?.pk) {
      formData.domain = props.domain.pk as string;
      loadRecords();
    }
  }
);

/** 同步关闭状态 */
watch(drawerVisible, val => {
  if (!val) emit("update:visible", false);
});

/** 加载解析记录列表 */
const loadRecords = async () => {
  if (!props.domain?.pk) return;
  loading.value = true;
  try {
    const res: any = await dnsRecordApi.list({
      page: 1,
      size: 1000,
      domain: props.domain.pk
    });
    if (res.code === 1000) {
      tableData.value = res.data.results || [];
    }
  } finally {
    loading.value = false;
  }
};

/** 提取 record_type 的原始值 */
const typeValue = (type: any): string => {
  if (!type) return "";
  if (typeof type === "object") return type.value || "";
  return type;
};

/** 记录类型标签颜色 */
const typeTagType = (type: any) => {
  const map: Record<string, any> = {
    A: "success",
    AAAA: "success",
    CNAME: "warning",
    MX: "danger",
    TXT: "info",
    NS: "",
    SRV: "danger",
    CAA: "info"
  };
  return map[typeValue(type)] || "";
};

const recordTypeLabel = (type: any) => {
  if (!type) return "";
  if (typeof type === "object") return type.label || "";
  return type;
};

/** 提取 {value, label} 对象的 label */
const fieldLabel = (val: any): string => {
  if (!val) return "";
  if (typeof val === "object") return val.label || val.value || "";
  return val;
};

/** 提取 {value, label} 对象的 value */
const fieldValue = (val: any): string => {
  if (!val) return "";
  if (typeof val === "object") return val.value || "";
  return val;
};

/** 解析 DNS 服务器列表（逗号/换行/空格分隔） */
const dnsServers = computed(() => {
  const raw = props.domain?.dns_server;
  if (!raw) return [];
  // 支持逗号、换行、分号、空格分隔
  return String(raw)
    .split(/[,;\n]+/)
    .map(s => s.trim())
    .filter(Boolean);
});

/** 重置表单 */
const resetForm = () => {
  formData.record_type = "A";
  formData.host = "@";
  formData.value = "";
  formData.ttl = 600;
  formData.priority = undefined;
  formData.is_active = true;
};

/** 新增 */
const handleAdd = () => {
  isEdit.value = false;
  formTitle.value = "新增解析记录";
  resetForm();
  formVisible.value = true;
};

/** 编辑 */
const handleEdit = (row: DnsRecordItem) => {
  isEdit.value = true;
  formTitle.value = "编辑解析记录";
  currentPk.value = row.pk;
  formData.record_type = typeValue(row.record_type);
  formData.host = row.host || "@";
  formData.value = row.value || "";
  formData.ttl = row.ttl || 600;
  formData.priority = row.priority;
  formData.is_active = row.is_active;
  formVisible.value = true;
};

/** 保存 */
const handleSave = async () => {
  if (!formData.value) {
    ElMessage.warning("请输入记录值");
    return;
  }
  formLoading.value = true;
  try {
    const data: any = {
      domain: props.domain.pk,
      record_type: formData.record_type,
      host: formData.host,
      value: formData.value,
      ttl: formData.ttl,
      is_active: formData.is_active
    };
    if (NEEDS_PRIORITY.includes(formData.record_type)) {
      data.priority = formData.priority || 0;
    }
    if (isEdit.value) {
      await dnsRecordApi.update(currentPk.value, data);
      ElMessage.success("记录更新成功");
    } else {
      await dnsRecordApi.create(data);
      ElMessage.success("记录创建成功");
    }
    formVisible.value = false;
    loadRecords();
  } finally {
    formLoading.value = false;
  }
};

/** 删除 */
const handleDelete = async (row: DnsRecordItem) => {
  await ElMessageBox.confirm(
    `确定删除解析记录 "${row.host} ${typeValue(row.record_type)} → ${row.value}"？`,
    "确认删除",
    { type: "warning" }
  );
  await dnsRecordApi.destroy(row.pk);
  ElMessage.success("删除成功");
  loadRecords();
};
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="`DNS 解析记录 - ${domain?.domain_name || ''}`"
    direction="rtl"
    size="65%"
    destroy-on-close
  >
    <!-- 域名信息 -->
    <div
      class="mb-4 p-4 rounded-lg bg-bg_color border border-[var(--el-border-color-lighter)]"
    >
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="域名">
          {{ domain?.domain_name }}
        </el-descriptions-item>
        <el-descriptions-item label="注册商">
          {{ domain?.registrar || "-" }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            v-if="fieldLabel(domain?.status)"
            :type="
              fieldValue(domain?.status) === 'active' ? 'success' : 'warning'
            "
            size="small"
          >
            {{ fieldLabel(domain?.status) }}
          </el-tag>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="DNS 服务器" :span="3">
          <template v-if="domain?.dns_server">
            <div
              v-for="(dns, idx) in dnsServers"
              :key="idx"
              class="text-xs font-mono"
            >
              {{ dns }}
            </div>
          </template>
          <span v-else>-</span>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 操作栏 -->
    <div class="mb-3 flex justify-between items-center">
      <span class="text-sm text-[var(--el-text-color-secondary)]">
        共 {{ tableData.length }} 条解析记录
      </span>
      <el-button
        type="primary"
        :icon="useRenderIcon('ri:add-line')"
        @click="handleAdd"
      >
        新增记录
      </el-button>
    </div>

    <!-- 解析记录表格 -->
    <el-table v-loading="loading" :data="tableData" border stripe size="small">
      <el-table-column label="记录类型" width="85">
        <template #default="{ row }">
          <el-tag :type="typeTagType(row.record_type)" size="small">
            {{ recordTypeLabel(row.record_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="host"
        label="主机记录"
        min-width="110"
        show-overflow-tooltip
      />
      <el-table-column
        prop="value"
        label="记录值"
        min-width="180"
        show-overflow-tooltip
      />
      <el-table-column prop="ttl" label="TTL(s)" width="75">
        <template #default="{ row }">
          {{ row.ttl || 600 }}
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="70">
        <template #default="{ row }">
          {{
            NEEDS_PRIORITY.includes(typeValue(row.record_type))
              ? (row.priority ?? "-")
              : "-"
          }}
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="70">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? "启用" : "停用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="handleEdit(row)">
            编辑
          </el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无解析记录" :image-size="80" />
      </template>
    </el-table>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="formVisible"
      :title="formTitle"
      width="500px"
      append-to-body
      destroy-on-close
    >
      <el-form :model="formData" label-width="90px" label-position="right">
        <el-form-item label="记录类型" required>
          <el-select v-model="formData.record_type" style="width: 100%">
            <el-option
              v-for="item in recordTypes"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="主机记录" required>
          <el-input v-model="formData.host" placeholder="如 @、www、mail" />
        </el-form-item>
        <el-form-item label="记录值" required>
          <el-input
            v-model="formData.value"
            placeholder="如 192.168.1.1 或 example.com"
          />
        </el-form-item>
        <el-form-item label="TTL(秒)">
          <el-input-number
            v-model="formData.ttl"
            :min="1"
            :max="86400"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item
          v-if="NEEDS_PRIORITY.includes(formData.record_type)"
          label="优先级"
        >
          <el-input-number
            v-model="formData.priority"
            :min="0"
            :max="65535"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="formData.is_active"
            active-text="启用"
            inactive-text="停用"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>
