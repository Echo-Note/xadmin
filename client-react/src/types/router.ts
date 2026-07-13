/**
 * 路由与菜单相关类型定义
 *
 * 定义动态路由、菜单结构、权限校验等路由域的数据结构。
 *
 * 模块职责：路由域的类型约束，支撑动态路由和菜单权限系统。
 */

import type { ComponentType, LazyExoticComponent } from "react";

// ==================== 路由元信息 ====================

/** 路由元数据 */
export interface RouteMeta {
  /** 菜单标题 */
  title: string;
  /** 菜单图标 */
  icon?: string;
  /** 是否在菜单中显示 */
  showLink?: boolean;
  /** 排序权重（越小越靠前） */
  rank?: number;
  /** 是否缓存页面 */
  keepAlive?: boolean;
  /** 所需角色 */
  roles?: string[];
  /** 所需权限标识 */
  auths?: string[];
  /** 是否固定标签页 */
  affix?: boolean;
  /** 外部链接 */
  isLink?: string;
  /** 是否全屏 */
  isFull?: boolean;
  /** 是否嵌入 iframe */
  isIframe?: boolean;
  /** iframe 地址 */
  frameSrc?: string;
  /** 过渡动画名称 */
  transitionName?: string;
  /** 隐藏标签页 */
  hiddenTag?: boolean;
  /** 动态路由等级 */
  dynamicLevel?: number;
  /** 是否在面包屑中隐藏 */
  hiddenBreadcrumb?: boolean;
  /** 激活的菜单路径 */
  activePath?: string;
}

// ==================== 路由配置类型 ====================

/** 单个路由配置 */
export interface RouteConfig {
  /** 路由路径 */
  path: string;
  /** 路由名称（唯一标识） */
  name?: string;
  /** 页面组件（支持懒加载） */
  component?: LazyExoticComponent<ComponentType<unknown>> | ComponentType<unknown>;
  /** 重定向路径 */
  redirect?: string;
  /** 路由元信息 */
  meta?: RouteMeta;
  /** 子路由 */
  children?: RouteConfig[];
}

/** 后端返回的异步路由原始数据 */
export interface AsyncRoute {
  path: string;
  name: string;
  component: string;
  redirect?: string;
  meta: RouteMeta;
  children?: AsyncRoute[];
}

/** 获取异步路由的 API 响应 */
export interface AsyncRoutesResult {
  success: boolean;
  data: AsyncRoute[];
  auths: string[];
}

// ==================== 菜单类型 ====================

/** 菜单项（用于渲染侧边栏/顶部菜单） */
export interface MenuItem {
  /** 菜单路径 */
  path: string;
  /** 菜单名称（用于命名路由） */
  name?: string;
  /** 菜单标题 */
  title: string;
  /** 菜单图标 */
  icon?: string;
  /** 排序 */
  rank?: number;
  /** 是否显示 */
  showLink?: boolean;
  /** 子菜单 */
  children?: MenuItem[];
  /** 重定向 */
  redirect?: string;
  /** 父级路径 */
  parentPath?: string;
  /** 完整路径 */
  fullPath?: string;
}

// ==================== 标签页类型 ====================

/** 多标签页项 */
export interface TagItem {
  /** 标签页路径 */
  path: string;
  /** 标签页名称 */
  name?: string;
  /** 标签页标题 */
  title: string;
  /** 路由元信息 */
  meta?: RouteMeta;
  /** 查询参数 */
  query?: Record<string, string>;
  /** 路由参数 */
  params?: Record<string, string>;
}

// ==================== 组件映射表 ====================

/** 组件路径到组件的映射 */
export type ComponentMap = Record<string, LazyExoticComponent<ComponentType<unknown>>>;
