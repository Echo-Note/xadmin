# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

## Commonly Used Commands

### 环境初始化

```bash
# 一键初始化：Git hooks + 后端 + 前端依赖
make setup

# 或分步执行
make hooks     # 配置 .husky Git hooks (pre-commit lint + commit-msg 格式校验)
make server    # 安装后端依赖 (cd server && uv sync --group dev)
make client    # 安装前端依赖 (cd client && pnpm install)
```

### Docker 服务（PostgreSQL + Redis）

```bash
cd server
set -a; source ../.env; set +a
docker compose up -d --wait postgresql redis
```
Docker 地址通过根目录 `.env` 文件配置（模板 `.env.example`），默认远程 `tcp://172.16.30.120:2375`。使用本地 Docker 时删除 `.env` 或注释掉 `DOCKER_HOST`，并将 `config.yml` 中 `DB_HOST`/`REDIS_HOST` 改为 `127.0.0.1`。

### 后端 (server/)

```bash
cd server

# 数据库迁移
uv run python manage.py migrate

# 创建超级用户
uv run python manage.py createsuperuser

# 启动开发服务器 (端口 8896)
uv run python manage.py runserver 0.0.0.0:8896

# 代码检查与格式化 (Ruff)
uv run ruff check .
uv run ruff format .

# 运行测试
uv run pytest
```

### 前端 (client/)

```bash
cd client

# Node 版本管理 (nvm, 版本见 client/.nvmrc)
source $HOME/.nvm/nvm.sh && nvm use

# 启动开发服务器 (端口 8848)
pnpm dev

# 类型检查
pnpm typecheck

# 生产构建
pnpm build

# 代码检查 (ESLint + Prettier + Stylelint)
pnpm lint
```

### Celery Worker

```bash
cd server
uv run celery -A server worker -l info
```

### 清理

```bash
make clean  # 清理前后端缓存
```

## Architecture

### Monorepo 结构

```
xadmin/
├── server/          # Django 5.2 后端 (Python 3.12, uv)
├── client/          # Vue3 前端 (Vite, pnpm, Node 24)
├── client-react/    # React 版前端 (实验性)
├── .husky/          # Git hooks (pre-commit lint + commit-msg 格式校验)
└── .vscode/         # VS Code 调试配置 (支持前后端联调 F5 一键启动)
```

端口约定：前端 8848、后端 8896、PostgreSQL 5432、Redis 6379。前端 Vite 代理 `/api`、`/media`、`/api-docs` → `http://127.0.0.1:8896`，`/ws` → `ws://127.0.0.1:8896`。

### 后端架构 (server/)

#### 应用分层

业务应用按功能拆分，位于 `server/apps/`：

| 应用 | 职责 |
|------|------|
| `common` | **核心框架层**：基础模型、ViewSet 混入、序列化器、过滤器、加密字段、缓存、自动路由。放在 `INSTALLED_APPS` 最后，确保 `django ready` 时其他应用已加载 |
| `system` | 系统管理：用户、角色、菜单、部门、权限（字段/数据）、操作日志、登录日志 |
| `settings` | 系统设置：安全策略、邮件、短信、存储后端、IP 黑名单，支持可视化配置热更新 |
| `notifications` | 消息通知：站内信、系统消息、用户订阅 |
| `captcha` | 图片/音频/滑块验证码 |
| `message` | WebSocket 实时消息推送 |
| `company` | 公司主体管理（独立业务模块，被其他应用通过 FK 引用） |
| `cloud_platform` | 多云平台管理：腾讯云/阿里云/AWS/Azure/华为云/vCenter/美橙 |
| `sync` | 多云平台资源同步引擎：服务器、域名、DNS 记录、账户余额 |
| `asset` | 资产管理：云服务器、域名、本地物理服务器、本地虚拟机 |

新增业务应用需在 `server/settings/base.py` 的 `INSTALLED_APPS` 中注册（放在 `common` 之前），并创建 `urls.py` 手动注册路由。

#### BaseModelSet — 视图集核心

整个后端最关键的架构设计：通过 **Mixin 多重继承** 灵活组合功能，而非深层继承链。

```python
# 预组合 ViewSet 及其能力
BaseModelSet       = CreateAction + DestroyAction + UpdateAction + ListAction + DetailAction
                   + SearchFieldsAction + SearchColumnsAction + AppChoicesAction
                   + BatchDestroyAction + GenericViewSet
                   # → 全功能 CRUD（最常用）

OnlyListModelSet   = ListAction + DetailAction + ...   # → 只读列表
ListDeleteModelSet = DestroyAction + ListAction + ...   # → 只读 + 删除
DetailUpdateModelSet = UpdateAction + DetailAction       # → 仅详情 + 更新（如 userinfo）
NoDetailModelSet   = UpdateAction + DetailAction + ...   # → 无 detail 路由（配置类）
```

所有 Action Mixin 均将返回值封装为统一的 `ApiResponse(code=1000, data=..., detail=...)` 格式。实际 ViewSet 通过追加混入扩展能力：

```python
class UserViewSet(BaseModelSet, UploadFileAction, ImportExportDataAction): ...
class MenuViewSet(BaseModelSet, RankAction, ImportExportDataAction, ChoicesAction, CacheListResponseMixin): ...
```

关键扩展混入：
- **ImportExportDataAction**：Excel/CSV 导入导出，默认通过 Celery 异步执行（100条/批），无 worker 时自动降级为同步
- **FileUploadMixin**：通过 `FILE_UPLOAD_FIELDS` 配置自动生成文件上传 action，内容寻址去重（MD5）
- **RankAction**：批量排序 `POST /rank/`
- **AppChoicesAction**：自动发现 app 的 `choices.py` 枚举并暴露为接口

#### 三层权限体系

1. **菜单权限**：URL → 菜单匹配 → 角色/部门关联，在 `IsAuthenticated.has_permission()` 中校验
2. **字段权限**：`request.fields` 传入允许的字段列表，`BaseModelSerializer.get_allow_fields()` 裁剪序列化输出
3. **数据权限**：`BaseDataPermissionFilter` 规则引擎，支持 ALL/OWNER/OWNER_DEPARTMENT/OWNER_DEPARTMENTS/DEPARTMENTS/DATE/TABLE_*/JSON 等规则类型，AND/OR 模式组合

#### 基础模型继承链

```
models.Model
  ├── DbUuidModel (UUID 主键)
  ├── DbCharModel (字符串主键)
  └── DbBaseModel (created_time, updated_time, description)
        └── DbAuditModel (creator FK→User, modifier FK→User, dept_belong FK→DeptInfo)
```

实际业务模型继承 `DbAuditModel + DbUuidModel` 获得完整审计字段。`AutoCleanFileMixin` 在对象更新/删除时自动清理关联物理文件。

#### 序列化器模式

- `BaseModelSerializer`：Choice 字段自动返回 `{value, label}` 对象；关联字段通过 `BasePrimaryKeyRelatedField` 返回包含 pk/name 等属性的字典而非纯 ID
- **Tabs 分组**：`Meta.tabs` 定义标签页布局，`TabsColumn(label='基本信息', fields=[...])`
- **三层注释规范**：`verbose_name` → `help_text` → `db_comment`（Django 5.1+），所有序列化器字段必须显式设置 `label` 和 `help_text`，使用 `gettext_lazy as _` 包裹，文案用英文
- 参考标准：`apps/settings/serializers/basic.py`

#### 加密与安全

- **EncryptedTextField**（`apps/common/fields/encrypted.py`）：AES-256-CBC 数据库透明加解密，密钥优先使用业务专用 key 否则回退 `SECRET_KEY`
- **AES 前端对齐**：`CryptoJS.AES.encrypt(data, token).toString()`（OpenSSL Salted/CBC），对应后端 `AESCipherV2`
- **JWT 双 Token**：access token + refresh token，存储在 Cookie 中（`CookieJWTAuthentication`）

#### 配置管理

`server/server/conf.py` 实现三层配置加载：Python 默认值 → `config.yml` 文件覆盖 → 环境变量。`sysConfig` 全局单例从数据库 `SystemConfig` 表读取动态配置并缓存到 Redis。新增插件应用通过 `XADMIN_APPS` 配置项注册。

#### 路由注册

路由**手动注册**而非自动发现。使用 DRF `SimpleRouter` + 自定义 `NoDetailRouter`（只生成 list 级路由，适合单例资源如 userinfo）。每个 app 的 `urls.py` 手动 `router.register()` 各 ViewSet。

### 前端架构 (client/)

基于 [vue-pure-admin](https://yuexiaoliang.github.io/vue-pure-admin-doc/) 二次开发。

#### 路由系统

**静态路由 + 动态路由** 混合模式。静态路由从 `router/modules/*.ts` 自动导入（`home.ts`、`error.ts`）；动态路由从 `GET /api/system/routes` 获取，通过 `addAsyncRoutes()` 处理后 `router.addRoute()` 注入。路由守卫处理登录态校验、token 刷新、动态路由初始化。

三级及以上路由会被拍平为二级（因 keep-alive 仅支持二级缓存）。

#### 状态管理 (Pinia)

6 个 Store 模块：`user`（用户信息/登录/token）、`permission`（菜单路由/keep-alive/权限 auths）、`app`（侧边栏/布局/设备类型）、`multiTags`（多标签页管理）、`settings`/`epTheme`（主题配置）、`siteConfig`（后端站点配置）。

#### API 层

`PureHttp` 类（`utils/http/index.ts`）封装 Axios：请求拦截器自动附加 `Authorization: Bearer` header 并无感刷新 token；响应拦截器处理 401（区分 token 过期 code=40001 和 无权限 code=40002）。

`BaseApi` 基类（`api/base.ts`）提供标准 CRUD 方法（list/create/retrieve/update/partialUpdate/destroy/batchDestroy/exportData/importData），业务 API 模块继承即可。

#### 布局系统

支持 vertical（垂直侧边栏）、horizontal（水平导航）、mix（混合）三种布局，响应式断点自动切换（≤760px 移动端强制 vertical）。

#### 全局组件与指令

全局组件以 `Re` 前缀命名（`ReIcon`、`ReDialog`、`ReDrawer`）。自定义指令：`auth`（按钮权限控制）、`copy`、`longpress`、`ripple`。

### 编码规范

- **分模块实现**：按功能拆分为独立模块，单个文件不超过 500 行。禁止流水账式代码，公共逻辑必须抽取为可复用函数/类。
- **先查阅已有实现**：动手前必须先搜索代码库中是否存在可复用的方法、工具函数、基类或混入类（如 `BaseModelSet`、`BaseApi`、`BaseFilterSet`、`FileUploadMixin` 等），避免重复造轮子。
- **类型标注**：所有函数签名、方法参数和返回值必须添加完整类型标注（Python type hints、TypeScript 严格模式）。
- **注释信息**：公共函数/方法/类型必须添加 docstring 或注释，说明用途、参数和返回值。复杂业务流程（如多层权限判断、异步任务编排、数据同步流水线）必须添加清晰的步骤注释，说明每一步的目的和输入/输出。
- **错误处理**：严禁宽松的异常捕获（如裸 `except:`、`except Exception:`、静默吞掉异常）。捕获时必须指定具体异常类型，记录日志或向上传播并保留完整上下文（Python 用 `raise ... from exc`，TypeScript 用 `cause`）。只在确有必要且清楚后果时才捕获异常，不允许吞错。
- **Python 工具链**：Python 脚本必须使用 `uv run` 执行，Python 环境必须使用 `uv` 管理（依赖安装、虚拟环境、包锁定）。禁止直接使用 `python` 或 `pip` 命令。
- **第三方框架文档**：涉及第三方库/框架的 API、配置、用法时，必须先通过 Context7 工具查询最新官方文档，禁止凭记忆猜测 API 签名或参数。

### 提交规范

- **禁止跳过检查**：不允许使用 `--no-verify`、`--no-gpg-sign` 等跳过 Git hooks 的参数。pre-commit 和 commit-msg 校验必须通过。
- **存量问题也要修**：代码检查工具（ruff/ESLint/Prettier）发现的已有代码问题也必须一并修改，不允许只改新代码而忽略存量警告。
- Git hooks（`.husky/`）：pre-commit 对前端运行 `lint-staged`（ESLint+Prettier+Stylelint），对后端运行 `ruff check + ruff format --check`。commit-msg 校验格式 `<type>: <描述>`（type 限定：feat/fix/docs/style/refactor/perf/test/chore/ci/build/revert）。
- 所有注释、提交信息、PR 描述统一使用中文。`merge.ff = false`（禁止 fast-forward 合并）。
