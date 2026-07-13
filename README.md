# xadmin

基于 Django + Vue3 的 RBAC 权限管理系统（全栈仓库）。

## 项目结构

- `xadmin-server/` — 后端服务 (Django 5.2, Python 3.12, uv)
- `xadmin-client/` — 前端应用 (Vue3, Vite, pnpm)

## 快速开始

### 1. 克隆仓库

```bash
git clone --recursive https://github.com/Echo-Note/xadmin.git
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

### 3. 后端配置

```bash
cd xadmin-server

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

### 4. 前端配置

```bash
cd xadmin-client
pnpm install
```

## 开发调试

使用 VS Code 打开**根目录**，`.vscode/launch.json` 提供全栈调试配置：

| 配置 | 说明 |
|------|------|
| `Django: xadmin-server` | 后端断点调试（自动启动 Docker 前置服务） |
| `Vue: xadmin-client (Chrome)` | 前端 Chrome 断点调试 |
| `Vue: xadmin-client (Edge)` | 前端 Edge 断点调试 |
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
| `xadmin-server/docker-compose.yml` | Docker Compose 服务定义 | 是 |
| `xadmin-server/docker-compose.override.yml` | 开发环境端口映射覆盖 | 是 |

### 切换 Docker 服务器

修改 `.env` 中的 `DOCKER_HOST`，同时更新 `xadmin-server/config.yml` 中的 `DB_HOST` 和 `REDIS_HOST` 为对应服务器 IP 即可。

### 使用本地 Docker

删除 `.env` 文件（或注释掉 `DOCKER_HOST`），并在 `config.yml` 中设置 `DB_HOST: 127.0.0.1`、`REDIS_HOST: 127.0.0.1`。

## 更多文档

- [开发部署文档](https://docs.dvcloud.xin/)
- [Docker 容器化部署](https://docs.dvcloud.xin/guide/installation-docker.html)
- 后端详细说明: `xadmin-server/README.md`
- 前端详细说明: `xadmin-client/README.md`
