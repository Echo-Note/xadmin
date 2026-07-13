/**
 * 通用 API 响应类型定义
 *
 * 本模块定义了所有 API 接口的标准响应格式，
 * 使用泛型提供类型安全的数据结构约束。
 *
 * 模块职责：提供统一的响应类型，确保前后端数据交互的类型一致性。
 */

// ==================== 基础响应类型 ====================

/** 无数据返回的响应（如删除操作） */
export interface BaseResult {
  detail: string;
  code: number;
}

/** 带泛型数据的标准响应 */
export interface BaseResultWithData<T = unknown> extends BaseResult {
  data: T;
}

// ==================== 列表相关响应类型 ====================

/** 分页列表数据结构 */
export interface PaginatedList<T = unknown> {
  results: T[];
  total?: number;
}

/** 分页列表响应 */
export interface ListResult<T = unknown> extends BaseResult {
  data: PaginatedList<T>;
}

/** 普通数组列表响应 */
export interface DataListResult<T = unknown> extends BaseResult {
  data: T[];
}

/** 单条数据详情响应 */
export interface DetailResult<T = unknown> extends BaseResult {
  data: T;
}

// ==================== 字典与搜索类型 ====================

/** 选项字典（如状态枚举） */
export interface ChoicesResult extends BaseResult {
  choices_dict: Record<string, Record<string, string>>;
}

/** 搜索字段定义 */
export interface SearchField {
  key: string;
  label: string;
  input_type: string;
  help_text?: string;
  default?: unknown;
  choices?: Array<{ value: unknown; label: string }>;
}

/** 搜索字段列表响应 */
export interface SearchFieldsResult extends BaseResult {
  data: SearchField[];
}

/** 表格列定义 */
export interface SearchColumn {
  key: string;
  label: string;
  input_type: string;
  required: boolean;
  read_only: boolean;
  write_only: boolean;
  [key: string]: unknown;
}

/** 表格列定义响应 */
export interface SearchColumnsResult extends BaseResult {
  data: SearchColumn[];
}

// ==================== 请求参数类型 ====================

/** 通用查询参数 */
export interface QueryParams {
  page?: number;
  size?: number;
  ordering?: string;
  search?: string;
  [key: string]: unknown;
}

/** 批量操作参数 */
export interface BatchParams {
  pks: (number | string)[];
}

// ==================== 文件上传相关 ====================

/** 文件上传配置 */
export interface UploadConfig {
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}
