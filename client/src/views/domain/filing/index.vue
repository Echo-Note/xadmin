<script lang="ts" setup>
import { ref } from "vue";
import { useFiling } from "./utils/hook";

defineOptions({
  name: "Filing"
});

const rePlusPageRef = ref();
const {
  api,
  auth,
  addOrEditOptions,
  tableBarButtonsProps,
  operationButtonsProps,
  listColumnsFormat
} = useFiling(() => rePlusPageRef.value?.getSelectPks() ?? []);
</script>

<template>
  <RePlusPage
    ref="rePlusPageRef"
    :api="api"
    :auth="auth"
    locale-name="filing"
    :addOrEditOptions="addOrEditOptions"
    :tableBarButtonsProps="tableBarButtonsProps"
    :operationButtonsProps="operationButtonsProps"
    :listColumnsFormat="listColumnsFormat"
  />
</template>
