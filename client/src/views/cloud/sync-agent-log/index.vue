<script lang="ts" setup>
import { getCurrentInstance, reactive, shallowRef } from "vue";
import { useRoute } from "vue-router";
import { syncAgentLogApi } from "@/api/cloud_platform";
import { getDefaultAuths } from "@/router/utils";
import type { RePlusPageProps } from "@/components/RePlusPage";

defineOptions({
  name: "CloudPlatformSyncAgentLog"
});

const route = useRoute();
const api = reactive(syncAgentLogApi);

const instance = getCurrentInstance();
const auth = reactive(getDefaultAuths(instance));

/** 从 URL query 参数获取预设的 sync_record 筛选值 */
const recordFilter = route.query?.sync_record ? String(route.query.sync_record) : undefined;

/** 首次加载时自动注入 sync_record 筛选参数 */
const beforeSearchSubmit = (params: Record<string, any>) => {
  if (recordFilter && !params.sync_record) {
    params.sync_record = recordFilter;
  }
  return params;
};

const operationButtonsProps = shallowRef<Record<string, any>>({
  width: 200,
  showNumber: 2,
  buttons: [
    { code: "update", show: false },
    { code: "destroy", show: false },
    { code: "create", show: false },
  ]
});

const addOrEditOptions = shallowRef<RePlusPageProps["addOrEditOptions"]>({
  props: {
    minWidth: "600px",
    dialogDrawerOptions: { width: "600px" }
  }
});
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="cloudSyncAgentLog"
    :addOrEditOptions="addOrEditOptions"
    :operationButtonsProps="operationButtonsProps"
    :beforeSearchSubmit="beforeSearchSubmit"
    :immediate="true"
  />
</template>
