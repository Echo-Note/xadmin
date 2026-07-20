import { getCurrentInstance, reactive } from "vue";
import { sslCertificateApi } from "@/api/asset";
import { getDefaultAuths } from "@/router/utils";

export function useSslCertificate() {
  const api = reactive(sslCertificateApi);

  const instance = getCurrentInstance();
  const defaultAuths = getDefaultAuths(instance);

  const auth = reactive({
    ...defaultAuths,
    exportData: defaultAuths.exportData || defaultAuths.list
  });

  const addOrEditOptions = reactive({
    title: "SSL 证书详情",
    width: "40%",
    addDisplay: false,
    editDisplay: false
  });

  return {
    api,
    auth,
    addOrEditOptions
  };
}
