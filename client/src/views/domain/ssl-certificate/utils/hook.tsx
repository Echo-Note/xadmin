import { getCurrentInstance, reactive, shallowRef } from "vue";
import { ElMessage } from "element-plus";
import { sslCertificateApi } from "@/api/domain";
import { getDefaultAuths } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import {
  getColourTypeByIndex,
  type OperationProps,
  type RePlusPageProps
} from "@/components/RePlusPage";

export function useSslCertificate() {
  const api = reactive(sslCertificateApi);

  const instance = getCurrentInstance();
  const defaultAuths = getDefaultAuths(instance);

  const auth = reactive({
    ...defaultAuths,
    exportData: defaultAuths.exportData || defaultAuths.list
  });

  /** 将关联域名列渲染为可滚动标签列表，便于区分多个二级域名 */
  const renderDomainsTags = (value: Array<{ pk: string; label: string }>) => {
    if (!Array.isArray(value) || value.length === 0) return <span></span>;
    return (
      <el-scrollbar>
        <el-space wrap>
          {value.map((item, index) => (
            <el-tag
              key={item.pk}
              type={getColourTypeByIndex(index + 1)}
              effect="light"
            >
              {item.label}
            </el-tag>
          ))}
        </el-space>
      </el-scrollbar>
    );
  };

  /** 列表列格式化：关联域名渲染为标签 */
  const listColumnsFormat: RePlusPageProps["listColumnsFormat"] = columns => {
    columns.forEach(column => {
      if (column.prop === "domains_info") {
        column.cellRenderer = ({ row }) => renderDomainsTags(row.domains_info);
      }
    });
    return columns;
  };

  /** 详情列格式化：关联域名渲染为标签 */
  const detailColumnsFormat: RePlusPageProps["detailColumnsFormat"] =
    columns => {
      columns.forEach(column => {
        if (column.prop === "domains_info") {
          column.render = (value: Array<{ pk: string; label: string }>) =>
            renderDomainsTags(value);
        }
      });
      return columns;
    };

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
    operationButtonsProps,
    listColumnsFormat,
    detailColumnsFormat
  };
}
