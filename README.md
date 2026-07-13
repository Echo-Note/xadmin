# xadmin

基于 Django + Vue3 的 RBAC 权限管理系统（全栈仓库）。

## 项目结构

- `xadmin-server/` — 后端服务 (Django 5.2, Python 3.12, uv)
- `xadmin-client/` — 前端应用 (Vue3, Vite, pnpm)

## 快速开始

```bash
# 克隆仓库（含子模块）
git clone --recursive https://github.com/Echo-Note/xadmin.git

# 后端
cd xadmin-server
uv sync --group dev

# 前端
cd xadmin-client
pnpm install
```

详见各子目录 README。

## 开发调试

使用 VS Code 打开根目录，`.vscode/launch.json` 提供全栈调试配置：

- `Django: xadmin-server` — 后端断点调试
- `Vue: xadmin-client (Chrome)` — 前端断点调试
- `全栈调试: 前后端联调` — 同时启动前后端
