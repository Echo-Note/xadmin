import { getCurrentInstance, reactive, shallowRef, h } from "vue";
import { addDialog } from "@/components/ReDialog";
import { platformApi, credentialApi } from "@/api/cloud_platform";
import { getDefaultAuths, hasAuth } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import type {
  PageTableColumn,
  OperationProps,
  RePlusPageProps
} from "@/components/RePlusPage";
import CredentialDialog from "./CredentialDialog.vue";

export function usePlatform() {
  const api = reactive(platformApi);

  const auth = reactive({
    ...getDefaultAuths(getCurrentInstance()),
    credentialList: hasAuth("list:Credential"),
    credentialCreate: hasAuth("create:Credential"),
    credentialUpdate: hasAuth("update:Credential"),
    credentialDelete: hasAuth("destroy:Credential"),
    credentialDecrypt: hasAuth("decrypt:Credential")
  });

  /** 打开凭据管理弹窗 */
  const openCredentialDialog = (row: Record<string, any>) => {
    addDialog({
      title: `凭据管理 - ${row.name}`,
      width: "70%",
      draggable: true,
      fullscreen: true,
      fullscreenIcon: true,
      contentRenderer: () =>
        h(CredentialDialog, {
          platform: row,
          credentialApi,
          auth
        }),
      hideFooter: true
    });
  };

  const operationButtonsProps = shallowRef<OperationProps>({
    width: 260,
    buttons: [
      { code: "retrieve", show: false },
      {
        code: "custom",
        text: "凭据管理",
        icon: useRenderIcon("ri:key-2-line"),
        props: { type: "default" },
        show: auth.credentialList,
        onClick: ({ row }) => openCredentialDialog(row)
      }
    ]
  });

  const listColumnsFormat = (columns: PageTableColumn[]) => {
    // 平台类型显示中文
    const typeCol = columns.find(c => c.prop === "platform_type");
    if (typeCol) {
      typeCol.cellRenderer = ({ row }) => {
        const map: Record<string, string> = {
          tencent: "腾讯云",
          aliyun: "阿里云",
          aws: "AWS",
          azure: "Azure",
          huawei: "华为云",
          vcenter: "vCenter",
          meicheng: "美橙",
          other: "其他"
        };
        return map[row.platform_type] || row.platform_type;
      };
    }
    return columns;
  };

  const addOrEditOptions = shallowRef<RePlusPageProps["addOrEditOptions"]>({
    props: {
      minWidth: "600px",
      dialogDrawerOptions: {
        width: "600px"
      }
    }
  });

  return {
    api,
    auth,
    addOrEditOptions,
    listColumnsFormat,
    operationButtonsProps
  };
}
