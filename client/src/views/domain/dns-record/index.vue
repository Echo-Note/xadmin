<script lang="ts" setup>
import { getCurrentInstance, reactive, shallowRef } from "vue";
import { dnsRecordApi } from "@/api/domain";
import { getDefaultAuths } from "@/router/utils";
import type { RePlusPageProps } from "@/components/RePlusPage";

defineOptions({
  name: "DnsRecord"
});

const api = reactive(dnsRecordApi);

const instance = getCurrentInstance();
const defaultAuths = getDefaultAuths(instance);

const auth = reactive({
  ...defaultAuths,
  exportData: defaultAuths.exportData || defaultAuths.list,
  importData: defaultAuths.importData || defaultAuths.create
});

const addOrEditOptions = shallowRef<RePlusPageProps["addOrEditOptions"]>({
  props: {
    minWidth: "600px",
    dialogDrawerOptions: {
      width: "700px"
    }
  }
});
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="dnsRecord"
    :addOrEditOptions="addOrEditOptions"
  />
</template>
