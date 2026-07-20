import { getCurrentInstance, reactive, shallowRef } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { filingApi } from "@/api/domain";
import { getDefaultAuths } from "@/router/utils";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import type { OperationProps, RePlusPageProps } from "@/components/RePlusPage";

export function useFiling(getSelectedPks: () => string[]) {
  const api = reactive(filingApi);

  const instance = getCurrentInstance();
  const defaultAuths = getDefaultAuths(instance);

  const auth = reactive({
    ...defaultAuths,
    exportData: defaultAuths.exportData || defaultAuths.list,
    importData: defaultAuths.importData || defaultAuths.create
  });

  /** 表格顶部批量操作按钮 */
  const tableBarButtonsProps = shallowRef<OperationProps>({
    buttons: [
      {
        code: "icp-precheck-batch",
        text: "全部同步",
        props: {
          type: "primary",
          plain: true,
          icon: useRenderIcon("ri:search-eye-line")
        },
        show: -5,
        onClick: async () => {
          const pks = getSelectedPks();
          const isSelected = pks.length > 0;
          const confirmMsg = isSelected
            ? `确认对选中的 ${pks.length} 条记录执行 ICP 备案预检测？`
            : "确认对所有待检测的域名执行 ICP 备案预检测？\n" +
              "系统将在后台异步执行，最多同时检测 5 个域名，避免带宽暴增。";
          try {
            await ElMessageBox.confirm(confirmMsg, "批量备案预检测", {
              confirmButtonText: "确认执行",
              cancelButtonText: "取消",
              type: "warning"
            });
            const res = await filingApi.preCheckBatch(
              isSelected ? pks : undefined
            );
            if (res.code === 1000) {
              ElMessage.success(
                `批量预检测任务已提交（task_id: ${res.data?.task_id}），请稍后查看检测结果。`
              );
            } else {
              ElMessage.error(res.detail || "批量检测失败");
            }
          } catch {
            // 用户取消或请求异常，不做处理
          }
        }
      }
    ]
  });

  /** 单行操作按钮 */
  const operationButtonsProps = shallowRef<OperationProps>({
    width: 380,
    buttons: [
      {
        code: "icp-precheck",
        text: "ICP 预检测",
        props: {
          type: "warning",
          link: true,
          icon: useRenderIcon("ri:search-eye-line")
        },
        show: -10,
        onClick: async ({ row }) => {
          try {
            await ElMessageBox.confirm(
              `确认对域名「${row.domain_info?.domain_name || "未知"}」执行 ICP 备案预检测？\n` +
                "系统将自动检测 www 解析并抓取首页页脚内容。",
              "备案预检测",
              {
                confirmButtonText: "确认",
                cancelButtonText: "取消",
                type: "warning"
              }
            );
            const res = await filingApi.preCheck(row.pk);
            if (res.code === 1000) {
              const data = res.data || {};
              let msg = `检测结果：\n`;
              msg += `- www 解析：${data.has_www_record ? "存在" : "不存在"}\n`;
              msg += `- 检测结论：${data.conclusion || "无"}\n`;
              if (data.detected_numbers?.length) {
                msg += `- 检测到备案号：${data.detected_numbers.join("、")}\n`;
              }
              ElMessageBox.alert(msg, "ICP 预检测完成", {
                confirmButtonText: "知道了",
                type: data.detected_numbers?.length ? "success" : "warning"
              });
            } else {
              ElMessage.error(res.detail || "预检测失败");
            }
          } catch {
            // 用户取消或请求异常，不做处理
          }
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
    tableBarButtonsProps,
    operationButtonsProps
  };
}
