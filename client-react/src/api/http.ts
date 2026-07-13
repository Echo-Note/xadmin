/**
 * HTTP 请求客户端模块
 *
 * 封装 axios 实例，提供统一的请求/响应拦截器，
 * 处理 Token 注入、401 自动刷新、错误提示等通用逻辑。
 *
 * 模块职责：HTTP 通信基础设施，不包含业务逻辑。
 */

import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
  type AxiosResponse,
  AxiosError,
} from "axios";
import { getToken, getRefreshToken, setToken, removeToken } from "@/utils/auth";

/** 成功响应码 */
const SUCCESS_CODE = 1000;

/** Token 过期 / 未授权响应码 */
const UNAUTHORIZED_CODE = 1401;

/** 创建 axios 实例 */
const http: AxiosInstance = axios.create({
  baseURL: "/api",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ==================== 请求拦截器 ====================

http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 注入 Access Token
    const token = getToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // 设置语言头
    const lang = localStorage.getItem("app-language") || "zh-CN";
    if (config.headers) {
      config.headers["Accept-Language"] = lang;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// ==================== 响应拦截器 ====================

/** 是否正在刷新 Token（防止并发刷新） */
let isRefreshing = false;
/** 等待 Token 刷新的请求队列 */
let refreshQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

http.interceptors.response.use(
  (response: AxiosResponse) => {
    const { data } = response;
    // 非成功码统一视为业务异常
    if (data.code !== undefined && data.code !== SUCCESS_CODE) {
      return Promise.reject(new Error(data.detail || "请求失败"));
    }
    return data;
  },
  async (error: AxiosError) => {
    const { response, config } = error;

    // 401 未授权：尝试刷新 Token
    if (response?.status === 401 && config) {
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        // 无 refreshToken，直接跳转登录页
        removeToken();
        window.location.href = "/#/login";
        return Promise.reject(error);
      }

      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const res = await axios.post("/api/system/refresh", {
            refresh: refreshToken,
          });
          if (res.data.code === SUCCESS_CODE) {
            setToken(res.data.data);
            // 刷新成功，重放队列中的请求
            const newToken = res.data.data.access;
            refreshQueue.forEach(({ resolve }) => resolve(newToken));
            refreshQueue = [];
            // 重试当前请求
            if (config.headers) {
              config.headers.Authorization = `Bearer ${newToken}`;
            }
            return http(config);
          }
        } catch {
          // 刷新失败，清除登录态
          refreshQueue.forEach(({ reject }) => reject(error));
          refreshQueue = [];
          removeToken();
          window.location.href = "/#/login";
        } finally {
          isRefreshing = false;
        }
      } else {
        // 正在刷新中，将请求加入队列等待
        return new Promise((resolve, reject) => {
          refreshQueue.push({
            resolve: (token: string) => {
              if (config.headers) {
                config.headers.Authorization = `Bearer ${token}`;
              }
              resolve(http(config));
            },
            reject,
          });
        });
      }
    }

    // 其他错误统一处理
    const message = (response?.data as Record<string, unknown>)?.detail || error.message || "网络错误";
    console.error(`[HTTP Error] ${message}`);
    return Promise.reject(error);
  }
);

export { http, SUCCESS_CODE, UNAUTHORIZED_CODE };
export default http;
