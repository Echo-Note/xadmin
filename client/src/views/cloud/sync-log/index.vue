<script lang="ts" setup>
import { getCurrentInstance, reactive, shallowRef } from "vue";
import { useRoute } from "vue-router";
import { syncRecordApi } from "@/api/cloud_platform";
import { getDefaultAuths } from "@/router/utils";
import type { RePlusPageProps } from "@/components/RePlusPage";

defineOptions({
  name: "CloudPlatformSyncLog"
});

const route = useRoute();
const api = reactive(syncRecordApi);

const instance = getCurrentInstance();
const auth = reactive(getDefaultAuths(instance));

/** 从 URL query 参数获取预设的 platform 筛选值 */
const platformFilter = route.query?.platform ? String(route.query.platform) : undefined;

/** 首次加载时自动注入 platform 筛选参数 */
const beforeSearchSubmit = (params: Record<string, any>) => {
  if (platformFilter && !params.platform) {
    params.platform = platformFilter;
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
    minWidth: "700px",
    dialogDrawerOptions: { width: "700px" }
  }
});
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="cloudSyncLog"
    :addOrEditOptions="addOrEditOptions"
    :operationButtonsProps="operationButtonsProps"
    :beforeSearchSubmit="beforeSearchSubmit"
  />
</template>
