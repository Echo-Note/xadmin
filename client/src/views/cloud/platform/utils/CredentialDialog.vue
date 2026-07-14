<script lang="ts" setup>
import { ref, reactive, onMounted, h } from "vue";
import {
  ElTable,
  ElTableColumn,
  ElButton,
  ElTag,
  ElMessageBox,
  ElMessage,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElOption,
  ElDatePicker
} from "element-plus";
import { credentialApi } from "@/api/cloud_platform";
import type { BaseApi } from "@/api/base";
import { addDialog } from "@/components/ReDialog";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";

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
  platform: Record<string, any>;
  credentialApi: BaseApi;
  auth: Record<string, boolean>;
}>();

const loading = ref(false);
const tableData = ref<CredentialRecord[]>([]);
const formVisible = ref(false);
const formTitle = ref("新增凭据");
const formLoading = ref(false);
const isEdit = ref(false);
const currentPk = ref("");

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

/** 加载凭据列表 */
const loadCredentials = async () => {
  loading.value = true;
  try {
    const res: any = await credentialApi.list({
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
  // 清除敏感字段（编辑时需重新输入）
  formData.access_key = "";
  formData.access_secret = "";
  formData.username = "";
  formData.password = "";
  formData.api_token = "";
  formVisible.value = true;
};

/** 保存凭据 */
const handleSave = async () => {
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

    // 按凭据类型填充对应字段
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
      await credentialApi.update(currentPk.value, data);
      ElMessage.success("凭据更新成功");
    } else {
      await credentialApi.create(data);
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
  await ElMessageBox.confirm(`确定删除凭据 "${row.credential_name}"？`, "确认删除", {
    type: "warning"
  });
  await credentialApi.destroy(row.pk);
  ElMessage.success("删除成功");
  loadCredentials();
};

/** 解密查看凭据 */
const handleDecrypt = async (row: CredentialRecord) => {
  const res: any = await (credentialApi as any).decrypt(row.pk);
  if (res.code === 1000) {
    const data = res.data;
    const lines: string[] = [];
    if (data.access_key) lines.push(`Access Key: ${data.access_key}`);
    if (data.access_secret) lines.push(`Secret Key: ${data.access_secret}`);
    if (data.username) lines.push(`用户名: ${data.username}`);
    if (data.password) lines.push(`密码: ${data.password}`);
    if (data.api_token) lines.push(`Token: ${data.api_token}`);
    if (data.email) lines.push(`邮箱: ${data.email}`);
    if (data.extra_data)
      lines.push(`扩展数据: ${JSON.stringify(data.extra_data, null, 2)}`);

    addDialog({
      title: `凭据明文 - ${row.credential_name}`,
      width: "500px",
      contentRenderer: () =>
        h(
          "pre",
          {
            style: {
              padding: "16px",
              background: "#f5f7fa",
              borderRadius: "4px",
              whiteSpace: "pre-wrap",
              wordBreak: "break-all"
            }
          },
          lines.join("\n")
        ),
      hideFooter: true
    });
  }
};

/** 凭据类型标签颜色 */
const typeTagType = (type: string) => {
  const map: Record<string, any> = {
    access_key: "success",
    password: "warning",
    api_token: "info"
  };
  return map[type] || "";
};

const typeLabel = (type: string) => {
  const map: Record<string, string> = {
    access_key: "密钥对",
    password: "密码",
    api_token: "Token"
  };
  return map[type] || type;
};

onMounted(() => {
  loadCredentials();
});
</script>

<template>
  <div style="min-height: 400px">
    <!-- 操作栏 -->
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between">
      <span style="font-weight: 500; color: #606266">
        平台：{{ platform.name }}
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
    <el-table :data="tableData" v-loading="loading" border stripe>
      <el-table-column prop="credential_name" label="凭据名称" min-width="140" />
      <el-table-column prop="credential_type" label="凭据类型" width="120">
        <template #default="{ row }">
          <el-tag :type="typeTagType(row.credential_type)" size="small">
            {{ typeLabel(row.credential_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="email" label="邮箱" width="180" />
      <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? "启用" : "禁用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
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
    </el-table>

    <!-- 新增/编辑凭据对话框 -->
    <el-dialog
      v-model="formVisible"
      :title="formTitle"
      width="550px"
      destroy-on-close
    >
      <el-form
        :model="formData"
        label-width="110px"
        label-position="right"
      >
        <el-form-item label="凭据名称" required>
          <el-input v-model="formData.credential_name" placeholder="如：运维账号" />
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

        <!-- Access Key 类型字段 -->
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

        <!-- 用户名密码类型字段 -->
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

        <!-- API Token 类型字段 -->
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
          <el-input v-model="formData.email" placeholder="关联邮箱（如美橙等需要）" />
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
          <el-switch v-model="formData.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
