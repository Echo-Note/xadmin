<script lang="ts" setup>
import { getCurrentInstance, reactive, shallowRef } from "vue";
import { companyApi } from "@/api/company";
import { getDefaultAuths } from "@/router/utils";
import type {
  PageTableColumn,
  RePlusPageProps
} from "@/components/RePlusPage";

defineOptions({
  name: "CompanyInstance"
});

const api = reactive(companyApi);

const auth = reactive({
  ...getDefaultAuths(getCurrentInstance())
});

const addOrEditOptions = shallowRef<RePlusPageProps["addOrEditOptions"]>({
  props: {
    minWidth: "500px",
    dialogDrawerOptions: {
      width: "500px"
    }
  }
});

const listColumnsFormat = (columns: PageTableColumn[]) => {
  return columns;
};
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="company"
    :addOrEditOptions="addOrEditOptions"
    :listColumnsFormat="listColumnsFormat"
  />
</template>
