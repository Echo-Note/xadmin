<script lang="ts" setup>
import { ref, reactive, watch } from "vue";
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
  ElSelect,
  ElOption,
  ElDatePicker,
  ElSwitch,
  ElDescriptions,
  ElDescriptionsItem,
  ElEmpty
} from "element-plus";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import type { BaseApi } from "@/api/base";

interface CredentialRecord {
  pk: string;
  credential_name: string;
  credential_type: string;
  username?: string;
  email?: string;
  remark?: string;
  token_expire_time?: string;
  is_active: boolean;
  platform: string;
}

const props = defineProps<{
  visible: boolean;
  platform: Record<string, any>;
  credentialApi: BaseApi;
  auth: Record<string, boolean>;
}>();

const emit = defineEmits<{
  (e: "update:visible", val: boolean): void;
}>();

const drawerVisible = ref(props.visible);
const loading = ref(false);
const tableData = ref<CredentialRecord[]>([]);
const formVisible = ref(false);
const formTitle = ref("新增凭据");
const formLoading = ref(false);
const isEdit = ref(false);
const currentPk = ref("");

/** 解密明文弹窗 */
const decryptVisible = ref(false);
const decryptData = ref<Record<string, any>>({});
const decryptTitle = ref("");

const formData = reactive({
  credential_name: "",
  credential_type: "access_key",
  access_key: "",
  access_secret: "",
  username: "",
  password: "",
  email: "",
  api_token: "",
  token_expire_time: null as string | null,
  remark: "",
  is_active: true
});

const credentialTypes = [
  { value: "access_key", label: "Access Key 密钥对" },
  { value: "password", label: "用户名/密码" },
  { value: "api_token", label: "API Token" }
];

/** 监听 visible 变化 */
watch(
  () => props.visible,
  val => {
    drawerVisible.value = val;
    if (val && props.platform?.pk) {
      loadCredentials();
    }
  }
);

/** 监听 drawerVisible 变化，同步到父组件 */
watch(drawerVisible, val => {
  if (!val) emit("update:visible", false);
});

/** 加载凭据列表 */
const loadCredentials = async () => {
  loading.value = true;
  try {
    const res: any = await props.credentialApi.list({
      page: 1,
      size: 1000,
      platform: props.platform.pk
    });
    if (res.code === 1000) {
      tableData.value = res.data.results;
    }
  } finally {
    loading.value = false;
  }
};

/** 重置表单 */
const resetForm = () => {
  formData.credential_name = "";
  formData.credential_type = "access_key";
  formData.access_key = "";
  formData.access_secret = "";
  formData.username = "";
  formData.password = "";
  formData.email = "";
  formData.api_token = "";
  formData.token_expire_time = null;
  formData.remark = "";
  formData.is_active = true;
};

/** 新增凭据 */
const handleAdd = () => {
  isEdit.value = false;
  formTitle.value = "新增凭据";
  resetForm();
  formVisible.value = true;
};

/** 编辑凭据 */
const handleEdit = (row: CredentialRecord) => {
  isEdit.value = true;
  formTitle.value = "编辑凭据";
  currentPk.value = row.pk;
  formData.credential_name = row.credential_name || "";
  formData.credential_type = row.credential_type || "access_key";
  formData.email = row.email || "";
  formData.remark = row.remark || "";
  formData.is_active = row.is_active;
  formData.token_expire_time = row.token_expire_time || null;
  formData.access_key = "";
  formData.access_secret = "";
  formData.username = "";
  formData.password = "";
  formData.api_token = "";
  formVisible.value = true;
};

/** 保存凭据 */
const handleSave = async () => {
  if (!formData.credential_name) {
    ElMessage.warning("请输入凭据名称");
    return;
  }
  formLoading.value = true;
  try {
    const data: any = {
      platform: props.platform.pk,
      credential_name: formData.credential_name,
      credential_type: formData.credential_type,
      email: formData.email,
      remark: formData.remark,
      is_active: formData.is_active,
      token_expire_time: formData.token_expire_time || undefined
    };

    if (formData.credential_type === "access_key") {
      data.access_key = formData.access_key;
      data.access_secret = formData.access_secret;
    } else if (formData.credential_type === "password") {
      data.username = formData.username;
      if (formData.password) data.password = formData.password;
    } else if (formData.credential_type === "api_token") {
      if (formData.api_token) data.api_token = formData.api_token;
    }

    if (isEdit.value) {
      await props.credentialApi.update(currentPk.value, data);
      ElMessage.success("凭据更新成功");
    } else {
      await props.credentialApi.create(data);
      ElMessage.success("凭据创建成功");
    }
    formVisible.value = false;
    loadCredentials();
  } finally {
    formLoading.value = false;
  }
};

/** 删除凭据 */
const handleDelete = async (row: CredentialRecord) => {
  await ElMessageBox.confirm(
    `确定删除凭据 "${row.credential_name}"？`,
    "确认删除",
    { type: "warning" }
  );
  await props.credentialApi.destroy(row.pk);
  ElMessage.success("删除成功");
  loadCredentials();
};

/** 解密查看凭据 */
const handleDecrypt = async (row: CredentialRecord) => {
  const res: any = await (props.credentialApi as any).decrypt(row.pk);
  if (res.code === 1000) {
    decryptData.value = res.data;
    decryptTitle.value = row.credential_name;
    decryptVisible.value = true;
  }
};

/** 凭据类型标签颜色 */
/** 提取 credential_type 的原始值（后端返回 {value, label} 对象） */
const typeValue = (type: any): string => {
  if (!type) return "";
  if (typeof type === "object") return type.value || "";
  return type;
};

const typeTagType = (type: any) => {
  const map: Record<string, any> = {
    access_key: "success",
    password: "warning",
    api_token: "info"
  };
  return map[typeValue(type)] || "";
};

const typeLabel = (type: any) => {
  if (!type) return "";
  if (typeof type === "object") return type.label || "";
  const map: Record<string, string> = {
    access_key: "密钥对",
    password: "密码",
    api_token: "Token"
  };
  return map[type] || type;
};

/** 平台类型显示 */
const platformTypeLabel = (type: any) => {
  if (!type) return "";
  if (typeof type === "object") return type.label || "";
  const map: Record<string, string> = {
    tencent: "腾讯云",
    aliyun: "阿里云",
    aws: "AWS",
    azure: "Azure",
    huawei: "华为云",
    vcenter: "vCenter",
    meicheng: "美橙",
    other: "其他"
  };
  return map[type] || type;
};
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="`凭据管理 - ${platform?.name || ''}`"
    direction="rtl"
    size="70%"
    destroy-on-close
  >
    <!-- 平台信息卡片 -->
    <div
      class="mb-4 p-4 rounded-lg bg-bg_color border border-[var(--el-border-color-lighter)]"
    >
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="平台名称">
          {{ platform?.name }}
        </el-descriptions-item>
        <el-descriptions-item label="平台类型">
          {{ platformTypeLabel(platform?.platform_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            :type="platform?.is_active ? 'success' : 'danger'"
            size="small"
          >
            {{ platform?.is_active ? "启用" : "禁用" }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 操作栏 -->
    <div class="mb-3 flex justify-between items-center">
      <span class="text-sm text-[var(--el-text-color-secondary)]">
        共 {{ tableData.length }} 条凭据
      </span>
      <el-button
        v-if="auth.credentialCreate"
        type="primary"
        :icon="useRenderIcon('ri:add-line')"
        @click="handleAdd"
      >
        新增凭据
      </el-button>
    </div>

    <!-- 凭据表格 -->
    <el-table v-loading="loading" :data="tableData" border stripe>
      <el-table-column
        prop="credential_name"
        label="凭据名称"
        min-width="120"
      />
      <el-table-column prop="credential_type" label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="typeTagType(row.credential_type)" size="small">
            {{ typeLabel(row.credential_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="username"
        label="用户名"
        width="100"
        show-overflow-tooltip
      />
      <el-table-column
        prop="email"
        label="邮箱"
        width="150"
        show-overflow-tooltip
      />
      <el-table-column
        prop="remark"
        label="备注"
        min-width="120"
        show-overflow-tooltip
      />
      <el-table-column prop="is_active" label="状态" width="70">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? "启用" : "禁用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.credentialDecrypt"
            link
            type="warning"
            size="small"
            @click="handleDecrypt(row)"
          >
            查看密钥
          </el-button>
          <el-button
            v-if="auth.credentialUpdate"
            link
            type="primary"
            size="small"
            @click="handleEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.credentialDelete"
            link
            type="danger"
            size="small"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无凭据数据" :image-size="80" />
      </template>
    </el-table>

    <!-- 新增/编辑凭据对话框 -->
    <el-dialog
      v-model="formVisible"
      :title="formTitle"
      width="520px"
      append-to-body
      destroy-on-close
    >
      <el-form :model="formData" label-width="100px" label-position="right">
        <el-form-item label="凭据名称" required>
          <el-input
            v-model="formData.credential_name"
            placeholder="如：运维账号"
          />
        </el-form-item>
        <el-form-item label="凭据类型" required>
          <el-select v-model="formData.credential_type" style="width: 100%">
            <el-option
              v-for="item in credentialTypes"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <template v-if="formData.credential_type === 'access_key'">
          <el-form-item label="Access Key" :required="!isEdit">
            <el-input
              v-model="formData.access_key"
              placeholder="请输入 Access Key ID"
            />
          </el-form-item>
          <el-form-item label="Secret Key" :required="!isEdit">
            <el-input
              v-model="formData.access_secret"
              type="password"
              show-password
              placeholder="请输入 Secret Access Key"
            />
          </el-form-item>
        </template>

        <template v-if="formData.credential_type === 'password'">
          <el-form-item label="用户名">
            <el-input v-model="formData.username" placeholder="请输入用户名" />
          </el-form-item>
          <el-form-item label="密码" :required="!isEdit">
            <el-input
              v-model="formData.password"
              type="password"
              show-password
              placeholder="请输入密码"
            />
          </el-form-item>
        </template>

        <template v-if="formData.credential_type === 'api_token'">
          <el-form-item label="API Token" :required="!isEdit">
            <el-input
              v-model="formData.api_token"
              type="password"
              show-password
              placeholder="请输入 API Token"
            />
          </el-form-item>
          <el-form-item label="过期时间">
            <el-date-picker
              v-model="formData.token_expire_time"
              type="datetime"
              placeholder="选择过期时间（可选）"
              style="width: 100%"
              value-format="YYYY-MM-DDTHH:mm:ss"
            />
          </el-form-item>
        </template>

        <el-form-item label="邮箱">
          <el-input
            v-model="formData.email"
            placeholder="关联邮箱（如美橙等需要）"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="formData.remark"
            type="textarea"
            :rows="2"
            placeholder="凭据用途说明"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch
            v-model="formData.is_active"
            active-text="启用"
            inactive-text="禁用"
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

    <!-- 解密明文对话框 -->
    <el-dialog
      v-model="decryptVisible"
      :title="`凭据明文 - ${decryptTitle}`"
      width="480px"
      append-to-body
    >
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item v-if="decryptData.access_key" label="Access Key">
          {{ decryptData.access_key }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="decryptData.access_secret"
          label="Secret Key"
        >
          {{ decryptData.access_secret }}
        </el-descriptions-item>
        <el-descriptions-item v-if="decryptData.username" label="用户名">
          {{ decryptData.username }}
        </el-descriptions-item>
        <el-descriptions-item v-if="decryptData.password" label="密码">
          {{ decryptData.password }}
        </el-descriptions-item>
        <el-descriptions-item v-if="decryptData.api_token" label="API Token">
          {{ decryptData.api_token }}
        </el-descriptions-item>
        <el-descriptions-item v-if="decryptData.email" label="邮箱">
          {{ decryptData.email }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="decryptData.token_expire_time"
          label="过期时间"
        >
          {{ decryptData.token_expire_time }}
        </el-descriptions-item>
        <el-descriptions-item v-if="decryptData.extra_data" label="扩展数据">
          {{ JSON.stringify(decryptData.extra_data) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </el-drawer>
</template>
