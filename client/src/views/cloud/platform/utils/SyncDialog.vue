<script lang="ts" setup>
import { ref, reactive } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { platformApi } from "@/api/cloud_platform";

interface Platform {
  pk: string;
  name: string;
  platform_type?: string | { value: string; label: string };
}

const props = defineProps<{
  platform: Platform;
}>();

const emit = defineEmits<{
  (e: "done"): void;
}>();

const visible = ref(false);
const loading = ref(false);

/** 资源选项 */
const resourceOptions = [
  { value: "server", label: "云服务器", icon: "ri:server-line" },
  { value: "domain", label: "域名", icon: "ri:global-line" },
  { value: "dns_record", label: "DNS 解析记录", icon: "ri:list-settings-line" },
  { value: "balance", label: "账户余额", icon: "ri:money-cny-circle-line" }
];

const selectedResources = ref<string[]>([]);

/** 打开对话框 */
const open = () => {
  // 默认全选
  selectedResources.value = resourceOptions.map(r => r.value);
  visible.value = true;
};

/** 关闭 */
const close = () => {
  visible.value = false;
};

/** 执行同步 */
const handleSync = async () => {
  if (selectedResources.value.length === 0) {
    ElMessage.warning("请至少选择一种资源类型");
    return;
  }
  loading.value = true;
  try {
    const res: any = await platformApi.triggerSync(
      props.platform.pk,
      selectedResources.value
    );
    if (res.code === 1000) {
      ElMessage.success(
        `同步任务已提交（任务ID: ${res.data?.task_id || "N/A"}），完成后将通过系统通知告知结果`
      );
      close();
      emit("done");
    } else {
      ElMessage.error(res.detail || "同步任务提交失败");
    }
  } catch {
    ElMessage.error("网络请求异常");
  } finally {
    loading.value = false;
  }
};

/** 刷新余额 */
const handleRefreshBalance = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要通过云厂商 API 异步刷新平台 "${props.platform.name}" 的账户余额吗？`,
      "确认刷新余额",
      { type: "info" }
    );
  } catch {
    return;
  }
  loading.value = true;
  try {
    const res: any = await platformApi.refreshBalance(props.platform.pk);
    if (res.code === 1000) {
      ElMessage.success("余额刷新任务已提交，完成后将通过系统通知告知结果");
      emit("done");
    } else {
      ElMessage.error(res.detail || "余额刷新失败");
    }
  } catch {
    ElMessage.error("网络请求异常");
  } finally {
    loading.value = false;
  }
};

/** 平台类型显示 */
const platformTypeLabel = (type: any) => {
  if (!type) return "";
  if (typeof type === "object") return type.label || "";
  const map: Record<string, string> = {
    tencent: "腾讯云", aliyun: "阿里云", aws: "AWS", azure: "Azure",
    huawei: "华为云", vcenter: "vCenter", meicheng: "美橙", other: "其他"
  };
  return map[type] || type;
};

defineExpose({ open, handleRefreshBalance });
</script>

<template>
  <el-dialog
    v-model="visible"
    title="触发资源同步"
    width="460px"
    append-to-body
    destroy-on-close
  >
    <!-- 平台信息 -->
    <div class="mb-4 p-3 rounded bg-[var(--el-fill-color-light)]">
      <div class="text-sm font-medium">{{ platform.name }}</div>
      <div class="text-xs text-[var(--el-text-color-secondary)] mt-1">
        {{ platformTypeLabel(platform.platform_type) }}
      </div>
    </div>

    <!-- 资源选择 -->
    <div class="mb-2 text-sm text-[var(--el-text-color-regular)]">
      请选择需要同步的资源类型：
    </div>
    <el-checkbox-group v-model="selectedResources" class="flex flex-col gap-2">
      <el-checkbox
        v-for="item in resourceOptions"
        :key="item.value"
        :value="item.value"
        :label="item.value"
        class="!mr-0"
      >
        <span class="flex items-center gap-1.5">
          <i :class="item.icon" />
          {{ item.label }}
        </span>
      </el-checkbox>
    </el-checkbox-group>

    <div class="mt-4 p-2 rounded bg-[var(--el-color-info-light-9)]">
      <div class="text-xs text-[var(--el-text-color-secondary)]">
        <i class="ri-information-line mr-1" />
        同步将在后台异步执行，完成后通过系统通知告知结果
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="loading"
        :icon="useRenderIcon('ri:refresh-line')"
        @click="handleSync"
      >
        开始同步
      </el-button>
    </template>
  </el-dialog>
</template>
