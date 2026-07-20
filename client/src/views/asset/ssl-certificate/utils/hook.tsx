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

  /** 证书详情/编辑配置（可编辑私钥，不可手动新增） */
  const addOrEditOptions = reactive({
    title: "SSL 证书详情",
    width: "60%",
    addDisplay: false,
    editDisplay: true
  });

  return {
    api,
    auth,
    addOrEditOptions
  };
}
