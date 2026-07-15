import { getCurrentInstance, reactive, shallowRef, ref } from "vue";
import { platformApi, credentialApi } from "@/api/cloud_platform";
import { getDefaultAuths, hasAuth } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import type {
  PageTableColumn,
  OperationProps,
  RePlusPageProps
} from "@/components/RePlusPage";

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

  /** 凭据管理抽屉状态 */
  const credentialDrawerVisible = ref(false);
  const currentPlatform = ref<Record<string, any>>({});

  /** 打开凭据管理抽屉 */
  const openCredentialDrawer = (row: Record<string, any>) => {
    currentPlatform.value = row;
    credentialDrawerVisible.value = true;
  };

  const operationButtonsProps = shallowRef<OperationProps>({
    width: 280,
    showNumber: 4,
    buttons: [
      { code: "retrieve", show: false },
      {
        code: "custom",
        text: "凭据",
        props: {
          type: "primary",
          link: true,
          icon: useRenderIcon("ri:key-2-line")
        },
        show: auth.credentialList && -15,
        onClick: ({ row }) => openCredentialDrawer(row)
      },
      {
        code: "detail",
        text: "查看",
        update: true,
        show: (auth.list || auth.retrieve) && -10
      }
    ]
  });

  const listColumnsFormat = (columns: PageTableColumn[]) => {
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
    operationButtonsProps,
    credentialDrawerVisible,
    currentPlatform,
    credentialApi
  };
}
