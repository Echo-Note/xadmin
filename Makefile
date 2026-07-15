.PHONY: setup hooks server client clean

# 一键初始化：配置 hooks + 安装前后端依赖
setup: hooks server client
	@echo ""
	@echo "🎉 初始化完成！"
	@echo "   git hooks: pre-commit (lint) + commit-msg (格式校验)"

# 配置 git hooks
hooks:
	@git config core.hooksPath .husky
	@chmod +x .husky/pre-commit .husky/commit-msg 2>/dev/null || true
	@echo "✅ git hooks 已配置 (core.hooksPath = .husky)"

# 安装后端依赖
server:
	@echo "📦 安装后端依赖 (server/)..."
	@cd server && uv sync --group dev
	@echo "✅ 后端依赖安装完成"

# 安装前端依赖
client:
	@echo "📦 安装前端依赖 (client/)..."
	@cd client && pnpm install
	@echo "✅ 前端依赖安装完成"

# 清理缓存
clean:
	@echo "🧹 清理缓存..."
	@cd server && uv clean 2>/dev/null || true
	@cd client && pnpm store prune 2>/dev/null || true
	@echo "✅ 清理完成"
