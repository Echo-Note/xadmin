<script lang="ts" setup>
import { useDomain } from "./utils/hook";
import DnsRecordDrawer from "./utils/DnsRecordDrawer.vue";
import RelationGraphDrawer from "./utils/RelationGraphDrawer.vue";

defineOptions({
  name: "Domain"
});

const {
  api,
  auth,
  addOrEditOptions,
  operationButtonsProps,
  dnsDrawerVisible,
  graphDrawerVisible,
  currentDomain
} = useDomain();
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="domain"
    :addOrEditOptions="addOrEditOptions"
    :operationButtonsProps="operationButtonsProps"
  />
  <DnsRecordDrawer v-model:visible="dnsDrawerVisible" :domain="currentDomain" />
  <RelationGraphDrawer
    v-model:visible="graphDrawerVisible"
    :domain="currentDomain"
  />
</template>
