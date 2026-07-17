import { BaseApi } from "@/api/base";
import { http } from "@/utils/http";
import type { BaseResult } from "@/api/types";

/** 云服务器资产 API */
export const cloudServerApi = new BaseApi("/api/asset/cloud-server");

/** 域名资产 API */
export const domainApi = new BaseApi("/api/asset/domain");

/** DNS 解析记录 API */
export const dnsRecordApi = new BaseApi("/api/asset/dns-record");

/** 本地物理服务器 API */
export const localServerApi = new BaseApi("/api/asset/local-server");

/** 本地虚拟主机 API */
export const localVmApi = new BaseApi("/api/asset/local-vm");

/** 备案信息 API */
class FilingApi extends BaseApi {
  /** 对单条记录执行 ICP 备案预检测 */
  preCheck = (pk: string) =>
    this.request<BaseResult>("post", {}, {}, `${this.baseApi}/${pk}/pre-check`);

  /** 批量执行 ICP 备案预检测（异步） */
  preCheckBatch = (filings?: string[]) =>
    this.request<BaseResult>(
      "post",
      {},
      filings ? { filings } : {},
      `${this.baseApi}/pre-check-batch`
    );
}
export const filingApi = new FilingApi("/api/asset/filing");

/** 资产关联图谱 API */
export const fetchRelationGraph = (domainPk: string) =>
  http.get<any, { data: { nodes: any[]; edges: any[] } }>(
    `/api/asset/relation-graph/?domain=${domainPk}`
  );
