<script lang="ts" setup>
import { useSslCertificate } from "./utils/hook";

defineOptions({
  name: "SslCertificate"
});

const { api, auth, addOrEditOptions } = useSslCertificate();
</script>

<template>
  <RePlusPage
    :api="api"
    :auth="auth"
    locale-name="ssl-certificate"
    :addOrEditOptions="addOrEditOptions"
  />
</template>
