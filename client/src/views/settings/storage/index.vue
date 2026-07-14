<script lang="ts" setup>
import { settingsStorageApi } from "@/api/system/settings";
import { computed } from "vue";
import { hasAuth } from "@/router/utils";
import Setting from "@/views/settings/components/settings/index.vue";
import type { settingItemProps } from "@/views/settings/components/settings/types";

defineOptions({
  name: "SettingStorage"
});

const settingData = computed<Array<settingItemProps>>(() => [
  {
    auth: {
      partialUpdate: hasAuth("partialUpdate:SettingStorage"),
      retrieve: hasAuth("retrieve:SettingStorage")
    },
    api: settingsStorageApi,
    localeName: "settingStorage",
    title: "media",
    queryParams: { category: "media" }
  },
  {
    auth: {
      partialUpdate: hasAuth("partialUpdate:SettingStorage"),
      retrieve: hasAuth("retrieve:SettingStorage")
    },
    api: settingsStorageApi,
    localeName: "settingStorage",
    title: "static",
    queryParams: { category: "static" }
  }
]);
</script>

<template>
  <setting :model-value="settingData" />
</template>
