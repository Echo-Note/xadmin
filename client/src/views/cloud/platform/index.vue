<script lang="ts" setup>
import { usePlatform } from "./utils/hook";
import CredentialDialog from "./utils/CredentialDialog.vue";

defineOptions({
  name: "CloudPlatformInstance"
});

const {
  api,
  auth,
  addOrEditOptions,
  listColumnsFormat,
  operationButtonsProps,
  credentialDrawerVisible,
  currentPlatform,
  credentialApi
} = usePlatform();
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="cloudPlatform"
    :addOrEditOptions="addOrEditOptions"
    :listColumnsFormat="listColumnsFormat"
    :operationButtonsProps="operationButtonsProps"
  />
  <CredentialDialog
    v-model:visible="credentialDrawerVisible"
    :platform="currentPlatform"
    :credentialApi="credentialApi"
    :auth="auth"
  />
</template>
