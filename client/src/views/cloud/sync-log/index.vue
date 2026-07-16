<script lang="ts" setup>
import { reactive, shallowRef, computed } from "vue";
import { useRoute } from "vue-router";
import { syncRecordApi } from "@/api/cloud_platform";
import { getDefaultAuths } from "@/router/utils";
import type { RePlusPageProps } from "@/components/RePlusPage";

defineOptions({
  name: "CloudPlatformSyncLog"
});

const route = useRoute();
const api = reactive(syncRecordApi);
const auth = reactive(getDefaultAuths(null) as any);

/** 从 URL query 参数获取预设的 platform 筛选值 */
const initPlatformFilter = computed(() => {
  const platform = route.query?.platform;
  return platform ? String(platform) : undefined;
});

/** 首次加载时自动注入 platform 筛选参数 */
const beforeSearchSubmit = (params: Record<string, any>) => {
  if (initPlatformFilter.value && !params.platform) {
    params.platform = initPlatformFilter.value;
  }
  return params;
};

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
    :beforeSearchSubmit="beforeSearchSubmit"
  />
</template>
