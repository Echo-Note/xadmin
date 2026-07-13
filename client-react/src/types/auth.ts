/**
 * 认证相关类型定义
 *
 * 定义登录、注册、Token 管理、用户信息等认证域的数据结构。
 *
 * 模块职责：认证域的类型约束，确保登录态管理的类型安全。
 */

// ==================== Token 相关类型 ====================

/** JWT Token 信息 */
export interface TokenInfo {
  /** 刷新令牌 */
  refresh: string;
  /** 访问令牌 */
  access: string;
  /** access token 有效期（秒） */
  access_token_lifetime: number;
  /** refresh token 有效期（秒） */
  refresh_token_lifetime: number;
}

/** Token 接口响应 */
export interface TokenResult {
  code: number;
  detail: string;
  data: TokenInfo;
}

/** 临时 Token（用于加密传输） */
export interface TempTokenResult {
  code: number;
  token: string;
  detail: string;
  lifetime?: number;
}

// ==================== 用户信息类型 ====================

/** 用户基本信息 */
export interface UserInfo {
  /** 主键 */
  pk: number;
  /** 用户名 */
  username: string;
  /** 头像 URL */
  avatar: string;
  /** 昵称 */
  nickname: string;
  /** 邮箱 */
  email: string;
  /** 手机号 */
  phone: string;
  /** 上次登录时间 */
  last_login: string;
  /** 性别 */
  gender: string;
  /** 注册日期 */
  date_joined: string;
  /** 未读消息数量 */
  unread_message_count: number;
  /** 是否激活 */
  is_active: boolean;
  /** 角色列表 */
  roles: string[];
}

/** 用户信息接口响应（含额外配置） */
export interface UserInfoResult {
  code: number;
  detail: string;
  data: UserInfo;
  choices_dict: Record<string, Record<string, string>>;
  password_rule: string;
  config: SystemConfig;
}

// ==================== 登录相关类型 ====================

/** 基础登录请求参数 */
export interface LoginBasicParams {
  username: string;
  password: string;
  /** 加密用的临时 token */
  token?: string;
}

/** 验证码登录请求参数 */
export interface LoginCodeParams {
  phone: string;
  code: string;
}

/** 登录认证配置 */
export interface AuthInfoResult {
  code: number;
  detail: string;
  data: AuthConfig;
}

/** 认证配置详情 */
export interface AuthConfig {
  access: boolean;
  captcha: boolean;
  token: boolean;
  encrypted: boolean;
  password: boolean;
  email: boolean;
  sms: boolean;
  basic: boolean;
  rate: string;
  [key: string]: unknown;
}

// ==================== 验证码相关类型 ====================

/** 图形验证码响应 */
export interface CaptchaResult {
  code: number;
  detail: string;
  captcha_image: string;
  captcha_key: string;
  length: number;
}

/** 短信/邮箱验证码配置 */
export interface VerifyCodeConfig {
  is_enabled: boolean;
  sms_enabled: boolean;
  email_enabled: boolean;
}

// ==================== 注册相关类型 ====================

/** 注册请求参数 */
export interface RegisterParams {
  username: string;
  password: string;
  confirm_password: string;
  email?: string;
  phone?: string;
}

// ==================== 系统配置类型 ====================

/** 系统全局配置 */
export interface SystemConfig {
  /** 是否开启前端水印 */
  FRONT_END_WEB_WATERMARK_ENABLED: boolean;
  [key: string]: unknown;
}

// ==================== 密码相关 ====================

/** 密码规则 */
export interface PasswordRule {
  min_length: number;
  max_length: number;
  require_uppercase: boolean;
  require_lowercase: boolean;
  require_digit: boolean;
  require_special: boolean;
}

/** 重置密码请求参数 */
export interface ResetPasswordParams {
  phone?: string;
  email?: string;
  code: string;
  new_password: string;
  confirm_password: string;
}

/** 登出请求参数 */
export interface LogoutParams {
  refresh: string;
}
