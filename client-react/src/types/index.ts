/**
 * 类型定义统一导出入口
 *
 * 汇总所有类型模块，提供单一导入点。
 * 使用方式：import type { UserInfo, RouteConfig } from '@/types';
 */

export type {
  // API 响应类型
  BaseResult,
  BaseResultWithData,
  PaginatedList,
  ListResult,
  DataListResult,
  DetailResult,
  ChoicesResult,
  SearchField,
  SearchFieldsResult,
  SearchColumn,
  SearchColumnsResult,
  QueryParams,
  BatchParams,
  UploadConfig,
} from "./api";

export type {
  // 认证类型
  TokenInfo,
  TokenResult,
  TempTokenResult,
  UserInfo,
  UserInfoResult,
  LoginBasicParams,
  LoginCodeParams,
  AuthInfoResult,
  AuthConfig,
  CaptchaResult,
  VerifyCodeConfig,
  RegisterParams,
  SystemConfig,
  PasswordRule,
  ResetPasswordParams,
  LogoutParams,
} from "./auth";

export type {
  // 路由类型
  RouteMeta,
  RouteConfig,
  AsyncRoute,
  AsyncRoutesResult,
  MenuItem,
  TagItem,
  ComponentMap,
} from "./router";

export type {
  // 状态管理类型
  DeviceType,
  LayoutMode,
  SidebarState,
  ViewportSize,
  AppState,
  AppActions,
  UserState,
  UserActions,
  PermissionState,
  PermissionActions,
  MultiTagsState,
  MultiTagsActions,
} from "./store";
