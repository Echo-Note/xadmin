<script lang="ts" setup>
import { usePlatform } from "./utils/hook";

defineOptions({
  name: "CloudPlatformInstance"
});

const {
  api,
  auth,
  addOrEditOptions,
  listColumnsFormat,
  operationButtonsProps
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
</template>
