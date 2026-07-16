import { BaseApi } from "@/api/base";
import { http } from "@/utils/http";

/** 云平台实例 API */
class PlatformApi extends BaseApi {
  /** 异步刷新余额 */
  refreshBalance = (pk: string) =>
    http.post(`${this.baseApi}/${pk}/refresh-balance`, {
      data: { async: true }
    });

  /** 触发资源同步 */
  triggerSync = (platform: string, resources?: string[], syncType = "manual") =>
    http.post("/api/cloud/sync-record/trigger", {
      data: { platform, resources, sync_type: syncType }
    });
}

export const platformApi = new PlatformApi("/api/cloud/platform");

/** 凭据管理 API */
class CredentialApi extends BaseApi {
  /** 解密查看凭据明文 */
  decrypt = (pk: string) =>
    this.request("post", {}, {}, `${this.baseApi}/${pk}/decrypt`);
}

export const credentialApi = new CredentialApi("/api/cloud/credential");

/** 同步记录 API */
export const syncRecordApi = new BaseApi("/api/cloud/sync-record");

/** 同步 Agent 日志 API */
export const syncAgentLogApi = new BaseApi("/api/cloud/sync-agent-log");
