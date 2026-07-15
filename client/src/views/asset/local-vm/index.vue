<script lang="ts" setup>
import { getCurrentInstance, reactive, shallowRef } from "vue";
import { localVmApi } from "@/api/asset";
import { getDefaultAuths } from "@/router/utils";
import type { RePlusPageProps } from "@/components/RePlusPage";

defineOptions({
  name: "LocalVM"
});

const api = reactive(localVmApi);

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
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="localVM"
    :addOrEditOptions="addOrEditOptions"
  />
</template>
