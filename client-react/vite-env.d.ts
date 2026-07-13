/// <reference types="vite/client" />

/** 环境变量类型声明 */
interface ImportMetaEnv {
  /** API 基础地址 */
  readonly VITE_API_BASE_URL: string;
  /** 应用标题 */
  readonly VITE_APP_TITLE: string;
  /** 路由模式 */
  readonly VITE_ROUTER_MODE: "hash" | "history";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
