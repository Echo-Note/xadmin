import { BaseApi } from "@/api/base";

/** 云服务器资产 API */
export const cloudServerApi = new BaseApi("/api/asset/cloud-server");

/** 本地物理服务器 API */
export const localServerApi = new BaseApi("/api/asset/local-server");

/** 本地虚拟主机 API */
export const localVmApi = new BaseApi("/api/asset/local-vm");
