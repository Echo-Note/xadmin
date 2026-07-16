import { getCurrentInstance, reactive, shallowRef, ref } from "vue";
import { useRouter } from "vue-router";
import { platformApi, credentialApi } from "@/api/cloud_platform";
import { getDefaultAuths, hasAuth } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import { ElMessage } from "element-plus";
import type {
  PageTableColumn,
  OperationProps,
  RePlusPageProps
} from "@/components/RePlusPage";
import SyncDialog from "./SyncDialog.vue";

export function usePlatform() {
  const api = reactive(platformApi);
  const router = useRouter();

  const instance = getCurrentInstance();
  const defaultAuths = getDefaultAuths(instance);

  const auth = reactive({
    ...defaultAuths,
    // 导入导出权限回退到 list/create（与后端 permission.py 行为一致）
    exportData: defaultAuths.exportData || defaultAuths.list,
    importData: defaultAuths.importData || defaultAuths.create,
    credentialList: hasAuth("list:Credential"),
    credentialCreate: hasAuth("create:Credential"),
    credentialUpdate: hasAuth("update:Credential"),
    credentialDelete: hasAuth("destroy:Credential"),
    credentialDecrypt: hasAuth("decrypt:Credential")
  });

  /** 凭据管理抽屉状态 */
  const credentialDrawerVisible = ref(false);
  const currentPlatform = ref<Record<string, any>>({});

  /** 同步对话框 ref */
  const syncDialogRef = shallowRef<InstanceType<typeof SyncDialog>>();

  /** 打开凭据管理抽屉 */
  const openCredentialDrawer = (row: Record<string, any>) => {
    currentPlatform.value = row;
    credentialDrawerVisible.value = true;
  };

  /** 打开同步对话框 */
  const openSyncDialog = (row: Record<string, any>) => {
    currentPlatform.value = row;
    // 确保对话框组件已挂载后再调用 open
    setTimeout(() => {
      syncDialogRef.value?.open();
    }, 50);
  };

  /** 刷新余额 */
  const handleRefreshBalance = async (row: Record<string, any>) => {
    currentPlatform.value = row;
    // 通过 SyncDialog 的 handleRefreshBalance 方法
    setTimeout(() => {
      syncDialogRef.value?.handleRefreshBalance();
    }, 50);
  };

  /** 跳转到同步日志页面（新 tab 打开，带平台筛选） */
  const goSyncLog = (row: Record<string, any>) => {
    const { href } = router.resolve({
      path: "/cloud/sync-log/index",
      query: { platform: row.pk as string },
    });
    window.open(href, "_blank", "noopener,noreferrer");
  };

  const operationButtonsProps = shallowRef<OperationProps>({
    width: 400,
    showNumber: 4,
    buttons: [
      { code: "retrieve", show: false },
      {
        code: "refresh-balance",
        text: "刷新余额",
        props: {
          type: "warning",
          link: true,
          icon: useRenderIcon("ri:money-cny-circle-line")
        },
        show: auth.update && -35,
        onClick: ({ row }) => handleRefreshBalance(row)
      },
      {
        code: "trigger-sync",
        text: "同步",
        props: {
          type: "success",
          link: true,
          icon: useRenderIcon("ri:refresh-line")
        },
        show: auth.update && -30,
        onClick: ({ row }) => openSyncDialog(row)
      },
      {
        code: "sync-log",
        text: "日志",
        props: {
          type: "info",
          link: true,
          icon: useRenderIcon("ri:history-line")
        },
        show: auth.list && -25,
        onClick: ({ row }) => goSyncLog(row)
      },
      {
        code: "credentials",
        text: "凭据",
        props: {
          type: "primary",
          link: true,
          icon: useRenderIcon("ri:key-2-line")
        },
        show: auth.credentialList && -20,
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
      },
      /** 提交成功后刷新列表 */
      beforeSubmit: ({ formData }) => {
        // 保留 sync_resources 参数（如果表单中有的话），传递给后端 perform_create/perform_update
        // 如果用户没有选择同步资源，则移除该参数
        if (formData.sync_resources && !Array.isArray(formData.sync_resources)) {
          delete formData.sync_resources;
        }
        return formData;
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
    credentialApi,
    syncDialogRef
  };
}
