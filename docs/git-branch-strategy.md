# Git 分支规划：三层分支模型

> 适用于 xadmin 仓库，定义分支职责、命名规范与协作流程

## 分支模型总览

```
                          ┌─────────────────────────────────────────────┐
                          │              CloudWeave (集成分支)            │
                          │   合并 main + app/*，承载跨层适配，日常开发主线  │
                          └──────┬──────────────────┬───────────────────┘
                                 │                  │
                    ┌────────────▼────────┐  ┌──────▼──────────────┐
                    │   main (基础设施)    │  │  app/* (应用分支族)   │
                    │ 模型基类/序列化器/   │  │ 业务模块 + 本模块迁移  │
                    │ 公共组件/配置（无迁移）│  │ 不含基础设施变更      │
                    └─────────────────────┘  └─────────────────────┘
```

三个层级单向流动：`main`（基底）→ `app/*`（扩展）→ `CloudWeave`（组装）。

## 分支定义

### main — 基础设施分支

| 属性 | 值 |
|------|-----|
| 职责 | 仓库基础设施与公共层维护 |
| 保护级别 | 受保护，仅接受 PR/MR 合入 |
| 允许内容 | ORM 基类模型字段、序列化器基类、公共组件（`apps/common/`）、全局配置（`settings/`）、CI/CD、依赖版本锁定 |
| 禁止内容 | 具体业务模块代码、**所有迁移文件**、前端业务页面 |

**迁移原则**：main 只改模型/序列化器代码，**不提交迁移文件**。迁移在各 app 分支内通过 `makemigrations` 生成并提交，确保迁移与业务模块同分支演进。
| 合并方向 | 仅向上合入 CloudWeave，**不反向合并**任何应用分支 |

**判定标准**：改动如果影响多个应用共享的基类或公共设施，属于 main；如果仅影响单一业务模块，属于 app/*。

### app/* — 应用开发分支族

| 属性 | 值 |
|------|-----|
| 命名格式 | `app/{模块名}`，如 `app/cloud_platform`、`app/company` |
| 职责 | 单一业务模块的独立开发 |
| 保护级别 | 受保护，团队协作通过子分支 PR 合入 |
| 允许内容 | 该模块的 models / serializers / views / **migrations** / fixtures / 前端页面 |
| 禁止内容 | 基类字段修改、公共组件改动、其他模块的代码 |
| 依赖关系 | 基于 `main` 创建，可通过 **rebase** 获取 main 的基类更新以生成迁移，但不 merge（避免引入无关提交） |

**关键约束**：app/* 分支保持「纯应用代码」，不含基础设施变更。基类更新时，app/* rebase main 获取最新基类代码，在本分支内 `makemigrations` 生成适配迁移并提交。

### CloudWeave — 集成分支

| 属性 | 值 |
|------|-----|
| 职责 | 集成 main 与各 app/* 分支，验证跨层兼容性 |
| 保护级别 | 受保护 |
| 允许内容 | 分支合并提交、集成测试修复 |
| 禁止内容 | 迁移文件（迁移在各 app/* 内生成）、基类改动、业务模块代码 |
| 合并方向 | 从 main 和 app/* 合入；发布时标记 tag |
| 日常开发 | 功能开发在 app/* 子分支上进行，完成后合入 CloudWeave 验证 |

**不生成迁移**：CloudWeave 仅做集成与验证，不在本分支上 `makemigrations`。迁移文件随 app/* 合并自然汇入。

## 命名规范

### 分支命名

| 类型 | 格式 | 示例 |
|------|------|------|
| 基础设施 | `main` | — |
| 应用模块 | `app/{模块名}` | `app/cloud_platform` |
| 集成 | `CloudWeave` | — |
| 功能开发 | `feature/{模块名}-{简述}` | `feature/cloud_platform-credential-decrypt` |
| 修复 | `fix/{模块名}-{简述}` | `fix/company-permission-name` |
| 预发布 | `release/{版本号}` | `release/v1.2.0` |
| 热修复 | `hotfix/{简述}` | `hotfix/login-aes-decrypt` |

### 功能子分支流向

```
feature/* ──PR──▶ app/{模块}     （应用功能 + 迁移）
feature/* ──PR──▶ main           （基础设施改动，无迁移）
```

功能子分支从目标分支切出，完成后通过 PR 合回，合后删除。

## 工作流

### 场景一：应用功能开发

```
1. git checkout app/cloud_platform
2. git checkout -b feature/cloud_platform-batch-import
3. ...开发...
4. git push origin feature/cloud_platform-batch-import
5. 发起 PR: feature/cloud_platform-batch-import → app/cloud_platform
6. Review 通过后合并，删除 feature 分支
7. 将 app/cloud_platform 合入 CloudWeave 验证集成
```

### 场景二：基础设施变更

```
1. git checkout main
2. git checkout -b feature/base-model-ordering
3. ...修改基类模型代码（不提交迁移）...
4. PR: feature/base-model-ordering → main
5. 合并后，将 main 合入 CloudWeave 验证集成
6. 各 app/* 分支 rebase main，生成本模块适配迁移：
     git checkout app/cloud_platform
     git rebase main
     cd server && uv run python manage.py makemigrations cloud_platform
     git add server/apps/cloud_platform/migrations/
     git commit -m "chore: 同步基类变更到 cloud_platform 迁移"
7. 将各 app/* 合入 CloudWeave 验证
```

**注意**：迁移在各 app/* 分支内生成并提交，不在 main 或 CloudWeave 上 `makemigrations`。main 仅含模型代码变更，迁移文件由各 app rebase main 后本地生成。

### 场景三：集成与发布

```
1. 确保 CloudWeave 已合入最新 main 和所有待发布 app/*
2. 解决集成冲突（如有）
3. 运行全量测试
4. git tag v1.2.0
5. git push origin v1.2.0
6. 如需发布分支: git checkout -b release/v1.2.0
```

## 合并规则

### 允许的合并方向

| 源 → 目标 | 方式 | 说明 |
|-----------|------|------|
| `feature/*` → `main` | PR / squash | 基础设施功能 |
| `feature/*` → `app/*` | PR / squash | 应用功能 |
| `main` → `CloudWeave` | merge --no-ff | 基础设施更新集成 |
| `app/*` → `CloudWeave` | merge --no-ff | 应用更新集成 |
| `CloudWeave` → `release/*` | merge --no-ff | 发布切出 |

### 禁止的合并方向

| 源 → 目标 | 原因 |
|-----------|------|
| `app/*` → `main` | 应用代码不应进入基础设施 |
| `CloudWeave` → `main` | 集成层含应用代码，会污染基础设施 |
| `CloudWeave` → `app/*` | 集成层含其他应用代码，会污染单一应用分支 |
| `main` → `app/*` | 禁止 merge（允许 rebase 获取基类更新） |

### 合并提交信息格式

```
merge: 合并 {源分支} {简述} 到 {目标分支}
```

示例：
- `merge: 合并 app/cloud_platform 平台开发分支到 CloudWeave 集成分支`
- `merge: 合并 main 基础设施更新到 CloudWeave`

功能 PR 合并使用 squash，提交信息遵循 `<type>: <描述>` 格式。

## 冲突处理

### app/* → CloudWeave 冲突

app/* 与 main 改动文件范围应保持不重叠（应用模块与公共层解耦）。若出现冲突：

1. 优先以 app/* 侧为准保留业务逻辑，以 main 侧为准保留基类定义
2. 冲突文件涉及基类（`apps/common/core/models.py` 等）时，以 main 侧为准
3. 冲突文件涉及业务模块时，以 app/* 侧为准

### main → CloudWeave 冲突

main 更新基类后，若 CloudWeave 上出现迁移相关冲突，说明迁移未在 app/* 内及时生成。处理方式：

```bash
# 回到对应 app/* 分支，rebase main 后重新生成迁移
git checkout app/cloud_platform
git rebase main
cd server
uv run python manage.py makemigrations cloud_platform
git add server/apps/cloud_platform/migrations/
git commit -m "chore: 同步基类变更到 cloud_platform 迁移"

# 再将 app/* 合入 CloudWeave
git checkout CloudWeave
git merge --no-ff app/cloud_platform
```

**原则**：迁移冲突始终回到 app/* 分支解决，不在 CloudWeave 上直接编辑迁移文件。

## 版本与标签

| 标签类型 | 格式 | 示例 |
|----------|------|------|
| 正式发布 | `v{主}.{次}.{修订}` | `v1.2.0` |
| 预发布 | `v{版本}-rc.{序号}` | `v1.2.0-rc.1` |
| 备份 | `backup/{描述}-{时间戳}` | `backup/cloud_platform-pre-restructure-20260715092757` |

发布标签打在 CloudWeave 上，标记可部署的集成状态。

## 分支保护建议

| 分支 | 规则 |
|------|------|
| `main` | 禁止 force-push，需 ≥1 review，CI 通过 |
| `app/*` | 禁止 force-push，需 ≥1 review |
| `CloudWeave` | 禁止 force-push，合入前需集成测试通过 |
| `feature/*` | 可 force-push（个人开发分支） |

## 当前分支清单

| 分支 | 末端 | 状态 |
|------|------|------|
| `main` | `37e7c81` | 基础设施，含 ORM 字段 `db_comment` / 序列化器 `label` |
| `app/cloud_platform` | `95a9b52` | 纯应用代码，云平台 + 公司主体管理模块 |
| `CloudWeave` | `da266fc` | 集成分支，已合并 main + app/cloud_platform（迁移随 app/* 汇入） |
| `feature/storage` | `629cd7b` | 存储设置功能（历史分支，待归档） |
