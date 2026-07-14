# xadmin

基于 Django + Vue3 的 RBAC 权限管理系统（monorepo 全栈仓库）。

## 功能特性

- **RBAC 权限管理**：基于角色的精细化权限控制，支持菜单级、API 级权限分配
- **用户管理**：用户增删改查、密码策略、登录失败锁定、多因素认证
- **系统配置**：邮件、短信、安全策略等可视化配置，热更新
- **消息通知**：站内消息、邮件、短信多渠道通知，WebSocket 实时推送
- **操作审计**：登录日志、操作日志、文件变更追踪
- **数据字典**：系统级数据字典管理
- **任务调度**：Celery 异步任务 + 定时任务管理
- **验证码**：图片验证码、音频验证码、滑块验证码
- **文件存储**：本地存储 / AWS S3 / 腾讯云 COS / MinIO 动态切换，可视化配置

## 技术栈

### 后端 (`server/`)

| 技术 | 版本 | 说明 |
|------|------|------|
| Python | >=3.12 | 运行环境 |
| Django | 5.2 | Web 框架 |
| DRF | 3.16 | REST API |
| Channels | 4.3 | WebSocket (ASGI) |
| Celery | 5.6 | 异步任务 |
| PostgreSQL | — | 主数据库 |
| Redis | — | 缓存 / 消息队列 / Channel Layer |
| django-storages | — | S3/COS 对象存储后端 |
| uv | — | 包管理工具 |

### 前端 (`client/`)

| 技术 | 版本 | 说明 |
|------|------|------|
| Node.js | 24.11 | 运行环境（通过 nvm 管理） |
| Vue | 3 | 前端框架 |
| Vite | — | 构建工具 |
| pnpm | — | 包管理工具 |
| vue-pure-admin | — | UI 基座（二次开发） |

## 项目结构

```
xadmin/
├── server/          # 后端服务 (Django, Python, uv)
├── client/          # 前端应用 (Vue3, Vite, pnpm)
├── client-react/    # React 版前端（实验性）
├── docs/            # 项目文档
├── .vscode/         # VS Code 配置（调试、任务）
├── .env.example     # Docker 配置模板
├── .gitignore
├── LICENSE
└── README.md
```

> `server/` 和 `client/` 均已纳入根仓库统一管理（monorepo 模式），单次克隆即可获取全部代码。

## 快速开始

### 前置要求

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/)（Python 包管理）
- [Node.js 24+](https://nodejs.org/)（建议通过 [nvm](https://github.com/nvm-sh/nvm) 管理）
- [pnpm](https://pnpm.io/)
- [Docker](https://www.docker.com/)（用于运行 PostgreSQL 和 Redis）

### 1. 克隆仓库

```bash
git clone https://github.com/Echo-Note/xadmin.git
cd xadmin
```

### 2. 配置 Docker 地址

Docker 可运行在本地或远程服务器，通过根目录 `.env` 文件配置：

```bash
cp .env.example .env
```

编辑 `.env`，修改 `DOCKER_HOST` 为你的 Docker 服务器地址：

```bash
# 远程 Docker (TCP)
DOCKER_HOST=tcp://172.16.30.120:2375

# 远程 Docker (SSH)
DOCKER_HOST=ssh://user@172.16.30.120

# 本地 Docker — 删除 .env 文件或注释掉 DOCKER_HOST 即可
```

> `.env` 文件已在 `.gitignore` 中忽略，不会提交到仓库，每人独立配置。

### 3. 启动 Docker 服务

```bash
cd server
# 加载 .env 中的 DOCKER_HOST，启动 PostgreSQL + Redis
set -a; source ../.env; set +a
docker compose up -d --wait postgresql redis
```

### 4. 后端配置与启动

```bash
cd server

# 安装依赖（含开发工具）
uv sync --group dev

# 复制配置文件
cp config_example.yml config.yml
```

编辑 `config.yml`，设置数据库和 Redis 连接信息。**`DB_HOST` 和 `REDIS_HOST` 需与 Docker 主机地址一致**：

```yaml
# 如果 Docker 在远程服务器 172.16.30.120
DB_HOST: 172.16.30.120
REDIS_HOST: 172.16.30.120

# 如果使用本地 Docker
DB_HOST: 127.0.0.1
REDIS_HOST: 127.0.0.1
```

初始化数据库并启动：

```bash
# 数据库迁移
uv run python manage.py migrate

# 创建超级用户
uv run python manage.py createsuperuser

# 启动开发服务器
uv run python manage.py runserver 0.0.0.0:8896
```

### 5. 前端配置与启动

```bash
cd client

# 安装依赖（通过 nvm 加载指定 Node 版本）
source $HOME/.nvm/nvm.sh && nvm use
pnpm install

# 启动开发服务器
pnpm dev
```

浏览器访问 `http://localhost:8848`，默认账号 `admin` / `admin123`。

## 开发调试

使用 VS Code 打开**根目录**，`.vscode/launch.json` 提供全栈调试配置：

| 配置 | 说明 |
|------|------|
| `Django: server` | 后端断点调试（自动启动 Docker 前置服务） |
| `Vue: client (Chrome)` | 前端 Chrome 断点调试 |
| `Vue: client (Edge)` | 前端 Edge 断点调试 |
| `全栈调试: 前后端联调 (Chrome)` | 同时启动后端 + 前端 Chrome |
| `全栈调试: 前后端联调 (Edge)` | 同时启动后端 + 前端 Edge |

### 启动流程

```
F5 启动调试
  ├─ Docker 任务: 加载 .env → docker compose up -d --wait postgresql redis
  │    └─ 等待 PostgreSQL + Redis 健康检查通过
  ├─ Django debugpy 启动 (端口 8896)
  └─ Vite dev server 启动 (端口 8848) → 浏览器打开
```

### 端口约定

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 Vite | 8848 | 开发服务器 |
| 后端 Django | 8896 | API 服务 |
| PostgreSQL | 5432 | 数据库（Docker 容器映射） |
| Redis | 6379 | 缓存/消息（Docker 容器映射） |

前端 Vite 代理配置：`/api`、`/media`、`/api-docs` → `http://127.0.0.1:8896`，`/ws` → `ws://127.0.0.1:8896`

## Docker 配置说明

### 文件结构

| 文件 | 作用 | 是否提交 |
|------|------|----------|
| `.env.example` | Docker 配置模板 | 是 |
| `.env` | 本地 Docker 配置（每人不同） | 否（.gitignore 忽略） |
| `server/docker-compose.yml` | Docker Compose 服务定义 | 是 |
| `server/docker-compose.override.yml` | 开发环境端口映射覆盖 | 是 |

### 切换 Docker 服务器

修改 `.env` 中的 `DOCKER_HOST`，同时更新 `server/config.yml` 中的 `DB_HOST` 和 `REDIS_HOST` 为对应服务器 IP 即可。

### 使用本地 Docker

删除 `.env` 文件（或注释掉 `DOCKER_HOST`），并在 `config.yml` 中设置 `DB_HOST: 127.0.0.1`、`REDIS_HOST: 127.0.0.1`。

## 代码质量

### 后端

- **代码检查与格式化**：[Ruff](https://docs.astral.sh/ruff/) (lint + format)
- **类型检查**：[basedpyright](https://docs.basedpyright.com/)
- **docstring 完整性**：ruff D100-D107 规则，要求所有公共模块/类/方法/函数添加 docstring
- **类型标注完整性**：ruff ANN001/ANN201/ANN202 规则，要求函数参数和返回值标注类型

```bash
cd server

# 代码检查
uv run ruff check .

# 代码格式化
uv run ruff format .
```

### 前端

- ESLint + Prettier

## 更多文档

- [在线预览](https://xadmin.dvcloud.xin/)（账号 `admin` / `admin123`）
- [开发部署文档](https://docs.dvcloud.xin/)
- [Docker 容器化部署](https://docs.dvcloud.xin/guide/installation-docker.html)
- 后端详细说明: [`server/README.md`](server/README.md)
- 前端详细说明: [`client/README.md`](client/README.md)
- 问题排查记录: [`docs/`](docs/)

## 许可证与版权声明

本项目基于 [MIT License](LICENSE) 开源。

### 版权归属

本项目由以下贡献者共同维护：

- **ly_13** — 项目发起者与核心开发者，创建了后端服务的绝大多数模块
- **laogao** (wadxf@live.com) — 参与部分模块开发
- **nineven** — 仓库维护与工程化改进
- 其他贡献者 — 详见 Git 提交历史

> **关于文件头部注释的说明**
>
> 在 2026 年 7 月的代码质量改进中（提交 `d1f1c9f`），为统一添加 Python docstring
> 和类型标注，移除了部分 Python 文件顶部的元信息注释块，包括 `author`、`date`、
> `project`、`filename` 等字段。受影响文件约 69 个，原始作者标注均为 **ly_13**。
>
> 这些文件的完整作者信息、创建日期和修改记录均完整保留在 Git 提交历史中，
> 可通过 `git log --follow <file>` 或 `git blame <file>` 查询。移除头部注释
> 仅出于代码风格统一目的，不改变任何版权归属。

### 引用与二次开发

依据 MIT License 条款，在复制、修改或分发本项目代码时：

1. 保留上述版权声明
2. 保留 [LICENSE](LICENSE) 全文
3. 可通过 Git 历史追溯原始作者贡献
