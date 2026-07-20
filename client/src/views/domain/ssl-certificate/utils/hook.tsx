import { getCurrentInstance, reactive, shallowRef } from "vue";
import { ElMessage } from "element-plus";
import { sslCertificateApi } from "@/api/domain";
import { getDefaultAuths } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import type { OperationProps, RePlusPageProps } from "@/components/RePlusPage";

export function useSslCertificate() {
  const api = reactive(sslCertificateApi);

  const instance = getCurrentInstance();
  const defaultAuths = getDefaultAuths(instance);

  const auth = reactive({
    ...defaultAuths,
    exportData: defaultAuths.exportData || defaultAuths.list
  });

  /** 证书详情/编辑配置（可编辑私钥，不可手动新增） */
  const addOrEditOptions = shallowRef<RePlusPageProps["addOrEditOptions"]>({
    props: {
      minWidth: "700px",
      dialogDrawerOptions: {
        width: "900px"
      }
    }
  });

  /** 单行操作按钮：导出证书文件 */
  const operationButtonsProps = shallowRef<OperationProps>({
    width: 420,
    buttons: [
      {
        code: "export-nginx",
        text: "NGINX",
        props: {
          type: "success",
          link: true,
          icon: useRenderIcon("ri:download-2-line")
        },
        show: -10,
        onClick: async ({ row }) => {
          try {
            await sslCertificateApi.exportCert(row.pk, "nginx");
            ElMessage.success("NGINX 证书文件下载中");
          } catch {
            ElMessage.error("导出失败，请确认证书文件是否完整");
          }
        }
      },
      {
        code: "export-apache",
        text: "Apache",
        props: {
          type: "warning",
          link: true,
          icon: useRenderIcon("ri:download-2-line")
        },
        show: -9,
        onClick: async ({ row }) => {
          try {
            await sslCertificateApi.exportCert(row.pk, "apache");
            ElMessage.success("Apache 证书文件下载中");
          } catch {
            ElMessage.error("导出失败，请确认证书文件是否完整");
          }
        }
      },
      {
        code: "export-caddy",
        text: "Caddy",
        props: {
          type: "info",
          link: true,
          icon: useRenderIcon("ri:download-2-line")
        },
        show: -8,
        onClick: async ({ row }) => {
          try {
            await sslCertificateApi.exportCert(row.pk, "caddy");
            ElMessage.success("Caddy 证书文件下载中");
          } catch {
            ElMessage.error("导出失败，请确认证书文件是否完整");
          }
        }
      }
    ]
  });

  return {
    api,
    auth,
    addOrEditOptions,
    operationButtonsProps
  };
}
