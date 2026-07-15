import { BaseApi } from "@/api/base";

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
