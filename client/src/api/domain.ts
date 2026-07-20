import { BaseApi } from "@/api/base";
import { http } from "@/utils/http";
import type { BaseResult } from "@/api/types";

/** 域名资产 API */
export const domainApi = new BaseApi("/api/domain/domain");

/** DNS 解析记录 API */
export const dnsRecordApi = new BaseApi("/api/domain/dns-record");

/** SSL 证书 API */
export const sslCertificateApi = new BaseApi("/api/domain/ssl-certificate");

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
export const filingApi = new FilingApi("/api/domain/filing");

/** 域名关联图谱 API */
export const fetchRelationGraph = (domainPk: string) =>
  http.get<any, { data: { nodes: any[]; edges: any[] } }>(
    `/api/domain/relation-graph/?domain=${domainPk}`
  );
