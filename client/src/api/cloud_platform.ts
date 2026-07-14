import { BaseApi } from "@/api/base";
import { http } from "@/utils/http";

/** 云平台实例 API */
export const platformApi = new BaseApi("/api/cloud/platform");

/** 凭据管理 API */
class CredentialApi extends BaseApi {
  /** 解密查看凭据明文 */
  decrypt = (pk: string) =>
    this.request("post", {}, {}, `${this.baseApi}/${pk}/decrypt`);
}

export const credentialApi = new CredentialApi("/api/cloud/credential");
