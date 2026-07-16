<script lang="ts" setup>
import { usePlatform } from "./utils/hook";
import CredentialDialog from "./utils/CredentialDialog.vue";
import SyncDialog from "./utils/SyncDialog.vue";

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
  credentialApi,
  syncDialogRef
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
  <SyncDialog
    v-if="currentPlatform.pk"
    ref="syncDialogRef"
    :platform="currentPlatform"
    @done="() => {}"
  />
</template>
