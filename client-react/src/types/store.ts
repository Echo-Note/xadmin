/**
 * 状态管理相关类型定义
 *
 * 定义全局 Store 中各模块的状态和操作接口，
 * 对应 Zustand store 的 State & Actions 类型。
 *
 * 模块职责：全局状态的类型约束，确保状态管理的类型安全。
 */

import type { UserInfo } from "./auth";
import type { MenuItem, TagItem, RouteMeta } from "./router";

// ==================== 应用状态 ====================

/** 设备类型 */
export type DeviceType = "mobile" | "desktop";

/** 布局模式 */
export type LayoutMode = "vertical" | "horizontal" | "mix";

/** 侧边栏状态 */
export interface SidebarState {
  /** 是否展开 */
  opened: boolean;
  /** 是否无动画 */
  withoutAnimation: boolean;
  /** 是否通过点击折叠按钮触发 */
  isClickCollapse: boolean;
}

/** 视口尺寸 */
export interface ViewportSize {
  width: number;
  height: number;
}

/** 应用 Store 状态 */
export interface AppState {
  /** 侧边栏状态 */
  sidebar: SidebarState;
  /** 布局模式 */
  layout: LayoutMode;
  /** 设备类型 */
  device: DeviceType;
  /** 视口尺寸 */
  viewportSize: ViewportSize;
}

/** 应用 Store 操作 */
export interface AppActions {
  /** 切换侧边栏展开/折叠 */
  toggleSidebar: (withoutAnimation?: boolean) => void;
  /** 关闭侧边栏 */
  closeSidebar: (withoutAnimation?: boolean) => void;
  /** 设置设备类型 */
  setDevice: (device: DeviceType) => void;
  /** 设置布局模式 */
  setLayout: (layout: LayoutMode) => void;
  /** 设置视口尺寸 */
  setViewportSize: (size: ViewportSize) => void;
}

// ==================== 用户状态 ====================

/** 用户 Store 状态 */
export interface UserState {
  /** 头像 */
  avatar: string;
  /** 用户名 */
  username: string;
  /** 昵称 */
  nickname: string;
  /** 邮箱 */
  email: string;
  /** 手机号 */
  phone: string;
  /** 角色列表 */
  roles: string[];
  /** 前端生成的验证码长度 */
  verifyCodeLength: number;
  /**
   * 登录页当前显示的组件
   * 0: 账户密码登录（默认）
   * 1: 手机验证码登录
   * 2: 二维码登录
   * 3: 注册
   * 4: 忘记密码
   */
  currentPage: number;
  /** 是否勾选了"记住我" */
  isRemembered: boolean;
  /** 免登录存储天数（默认 7 天） */
  loginDay: number;
  /** 未读消息数量 */
  noticeCount: number;
  /** WebSocket 实例（消息通知用） */
  websocket: WebSocket | null;
  /** 水印清除函数 */
  clearWatermark: (() => void) | null;
}

/** 用户 Store 操作 */
export interface UserActions {
  /** 设置头像 */
  setAvatar: (avatar: string) => void;
  /** 设置用户名 */
  setUsername: (username: string) => void;
  /** 设置昵称 */
  setNickname: (nickname: string) => void;
  /** 设置邮箱 */
  setEmail: (email: string) => void;
  /** 设置手机号 */
  setPhone: (phone: string) => void;
  /** 设置角色 */
  setRoles: (roles: string[]) => void;
  /** 设置验证码长度 */
  setVerifyCodeLength: (length: number) => void;
  /** 设置登录页当前显示的组件 */
  setCurrentPage: (page: number) => void;
  /** 设置是否记住我 */
  setIsRemembered: (remembered: boolean) => void;
  /** 设置免登录天数 */
  setLoginDay: (day: number) => void;
  /** 设置未读消息数 */
  setNoticeCount: (count: number) => void;
  /** 增加未读消息数 */
  incrementNoticeCount: (count?: number) => void;
  /** 用户登录 */
  login: (params: Record<string, unknown>, encrypted?: boolean) => Promise<unknown>;
  /** 获取用户信息 */
  fetchUserInfo: () => Promise<UserInfo>;
  /** 用户注册 */
  register: (params: Record<string, unknown>) => Promise<unknown>;
  /** 用户登出 */
  logout: () => Promise<void>;
  /** 刷新 Token */
  refreshToken: (data: Record<string, unknown>) => Promise<unknown>;
  /** 初始化 WebSocket 消息处理 */
  initWebSocket: () => void;
}

// ==================== 权限状态 ====================

/** 权限 Store 状态 */
export interface PermissionState {
  /** 静态菜单（始终显示的菜单） */
  constantMenus: MenuItem[];
  /** 完整菜单树（静态 + 动态，已过滤权限） */
  wholeMenus: MenuItem[];
  /** 扁平化路由列表（用于 keepAlive 等场景） */
  flatteningRoutes: RouteMeta[];
  /** 需要缓存的路由名称列表 */
  cachePageList: string[];
  /** 按钮级权限映射表 */
  permissionAuths: string[];
}

/** 权限 Store 操作 */
export interface PermissionActions {
  /** 设置全局权限列表 */
  setWholeAuths: (auths: string[]) => void;
  /** 组装完整菜单树 */
  setWholeMenus: (routes: MenuItem[]) => void;
  /** 管理页面缓存（添加/删除/刷新） */
  cacheOperate: (params: { mode: "add" | "delete" | "refresh"; name: string }) => void;
  /** 清空所有页面缓存 */
  clearAllCache: () => void;
}

// ==================== 多标签页状态 ====================

/** 多标签页 Store 状态 */
export interface MultiTagsState {
  /** 当前打开的标签页列表 */
  tags: TagItem[];
  /** 是否缓存标签页数据到 localStorage */
  isCache: boolean;
}

/** 多标签页 Store 操作 */
export interface MultiTagsActions {
  /**
   * 管理标签页
   * @param mode - 操作模式
   *   - 'equal': 设置为指定标签列表
   *   - 'push': 新增标签
   *   - 'splice': 删除标签
   *   - 'refresh': 刷新标签
   *   - 'close': 关闭标签
   *   - 'closeOther': 关闭其他标签
   *   - 'closeLeft': 关闭左侧标签
   *   - 'closeRight': 关闭右侧标签
   *   - 'closeAll': 关闭所有标签
   */
  handleTags: (mode: string, value?: TagItem | TagItem[]) => void;
  /** 设置是否缓存 */
  setCache: (cache: boolean) => void;
}
