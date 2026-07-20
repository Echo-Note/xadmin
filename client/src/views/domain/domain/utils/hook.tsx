import { getCurrentInstance, reactive, shallowRef, ref } from "vue";
import { domainApi } from "@/api/domain";
import { getDefaultAuths } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import type { OperationProps, RePlusPageProps } from "@/components/RePlusPage";

export function useDomain() {
  const api = reactive(domainApi);

  const instance = getCurrentInstance();
  const defaultAuths = getDefaultAuths(instance);

  const auth = reactive({
    ...defaultAuths,
    exportData: defaultAuths.exportData || defaultAuths.list,
    importData: defaultAuths.importData || defaultAuths.create
  });

  /** DNS 解析记录抽屉 */
  const dnsDrawerVisible = ref(false);
  /** 资产关联图谱抽屉 */
  const graphDrawerVisible = ref(false);
  const currentDomain = ref<Record<string, any>>({});

  const setCurrentDomain = (row: Record<string, any>) => {
    currentDomain.value = row;
  };

  const operationButtonsProps = shallowRef<OperationProps>({
    width: 380,
    showNumber: 5,
    buttons: [
      {
        code: "relation-graph",
        text: "图谱",
        props: {
          type: "success",
          link: true,
          icon: useRenderIcon("ri:mind-map")
        },
        show: -20,
        onClick: ({ row }) => {
          setCurrentDomain(row);
          graphDrawerVisible.value = true;
        }
      },
      {
        code: "dns-records",
        text: "解析记录",
        props: {
          type: "primary",
          link: true,
          icon: useRenderIcon("ri:list-check")
        },
        show: -10,
        onClick: ({ row }) => {
          setCurrentDomain(row);
          dnsDrawerVisible.value = true;
        }
      }
    ]
  });

  const addOrEditOptions = shallowRef<RePlusPageProps["addOrEditOptions"]>({
    props: {
      minWidth: "700px",
      dialogDrawerOptions: {
        width: "900px"
      }
    }
  });

  return {
    api,
    auth,
    addOrEditOptions,
    operationButtonsProps,
    dnsDrawerVisible,
    graphDrawerVisible,
    currentDomain
  };
}
