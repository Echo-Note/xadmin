<script lang="ts" setup>
import { getCurrentInstance, reactive, shallowRef } from "vue";
import { domainApi } from "@/api/asset";
import { getDefaultAuths } from "@/router/utils";
import type { RePlusPageProps } from "@/components/RePlusPage";

defineOptions({
  name: "Domain"
});

const api = reactive(domainApi);

const instance = getCurrentInstance();
const defaultAuths = getDefaultAuths(instance);

const auth = reactive({
  ...defaultAuths,
  exportData: defaultAuths.exportData || defaultAuths.list,
  importData: defaultAuths.importData || defaultAuths.create
});

const addOrEditOptions = shallowRef<RePlusPageProps["addOrEditOptions"]>({
  props: {
    minWidth: "700px",
    dialogDrawerOptions: {
      width: "900px"
    }
  }
});

// 搜索表单：每行 3 个字段（更宽的输入框）
const plusSearchProps: RePlusPageProps["plusSearchProps"] = {
  colProps: {
    xs: 24,
    sm: 24,
    md: 8,
    lg: 8,
    xl: 8
  }
};
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="domain"
    :addOrEditOptions="addOrEditOptions"
    :plusSearchProps="plusSearchProps"
  />
</template>
