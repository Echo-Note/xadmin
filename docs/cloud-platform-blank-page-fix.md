# 云平台实例页面空白问题排查与修复

## 问题现象

云平台实例页面（`/cloud/platform/index`）和公司管理页面（`/company/index`）打开后显示空白，无任何内容渲染。

## 排查过程

### 1. 前端渲染维度

检查 `RePlusPage` 组件模板，发现页面渲染受 `v-if="auth?.list"` 控制：

```vue
<!-- client/src/components/RePlusPage/src/index.vue:98 -->
<div v-if="auth?.list" class="main">
  <!-- 页面内容 -->
</div>
```

当 `auth.list` 为 `false` 时，整个页面不渲染。

### 2. 权限状态维度

`auth.list` 由 `getDefaultAuths()` 生成，其逻辑为：

```typescript
// client/src/router/utils.ts
function getDefaultAuths(suffix, auth = []) {
  if (isObject(suffix)) {
    suffix = suffix?.type?.name;  // 取组件名（defineOptions 中的 name）
  }
  const actions = ["list", "create", "update", "upload", "destroy",
    "retrieve", "exportData", "importData", "batchDestroy", "partialUpdate", ...auth];
  actions.forEach(key => {
    auths[key] = hasAuth(`${key}:${suffix}`);  // 如 list:CloudPlatformInstance
  });
  return auths;
}
```

`hasAuth` 检查 `permissionAuths` 中是否存在对应权限标识，而 `permissionAuths` 来自后端 `get_auths()` 返回的权限名列表。

### 3. 根因定位

对比前端组件名与后端权限名：

| 维度 | 前端 | 后端 init_menu.json | 是否匹配 |
|------|------|---------------------|----------|
| 权限后缀 | `CloudPlatformInstance`（组件名） | `CloudPlatform`（权限名后缀） | ✗ |
| 删除动作 | `destroy`（getDefaultAuths 固定） | `delete` | ✗ |

- 组件名 `CloudPlatformInstance`（`defineOptions({ name: "CloudPlatformInstance" })`）与后端权限后缀 `CloudPlatform` 不一致
- `getDefaultAuths` 生成 `hasAuth("list:CloudPlatformInstance")`，但后端权限名为 `list:CloudPlatform`
- 导致 `auth.list = false` → `v-if="auth?.list"` 不通过 → 页面空白

公司管理页面存在同样问题（`CompanyInstance` vs `Company`）。

## 修复方案

### 核心原则

统一遵循系统约定：**权限名 = `{action}:{菜单name}`**，且菜单 name = 组件 name = 路由 name（四者一致）。

参考系统现有页面（如 `SystemRole`）：
- 菜单 name：`SystemRole`
- 组件 name：`SystemRole`
- 权限名：`list:SystemRole`、`create:SystemRole`、`destroy:SystemRole` 等

### 具体改动

#### 后端 — 权限名对齐菜单名

**`server/apps/cloud_platform/fixtures/init_menu.json`**：

| 修改前 | 修改后 |
|--------|--------|
| `list:CloudPlatform` | `list:CloudPlatformInstance` |
| `create:CloudPlatform` | `create:CloudPlatformInstance` |
| `retrieve:CloudPlatform` | `retrieve:CloudPlatformInstance` |
| `update:CloudPlatform` | `update:CloudPlatformInstance` |
| `delete:CloudPlatform` | `destroy:CloudPlatformInstance` |

**`server/apps/company/fixtures/init_menu.json`**：

| 修改前 | 修改后 |
|--------|--------|
| `list:Company` | `list:CompanyInstance` |
| `create:Company` | `create:CompanyInstance` |
| `retrieve:Company` | `retrieve:CompanyInstance` |
| `update:Company` | `update:CompanyInstance` |
| `delete:Company` | `destroy:CompanyInstance` |

两处改动要点：
1. 权限后缀改为菜单 name（`CloudPlatformInstance` / `CompanyInstance`），与组件名一致
2. `delete:` 改为 `destroy:`，对齐 `getDefaultAuths` 的 action 列表

#### 前端 — 无需修改

前端 `hook.tsx` / `index.vue` 使用 `getDefaultAuths(getCurrentInstance())` 标准写法，与 `demo/book`、`system/role` 等页面完全一致，无需特殊处理。

### 数据库更新

```bash
# 重新初始化菜单（创建新权限名，旧权限名成为孤儿）
uv run python manage.py init -app apps.cloud_platform
uv run python manage.py init -app apps.company

# 清理旧孤儿权限
uv run python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'server.settings')
django.setup()
from apps.system.models import Menu
old = [
    'list:CloudPlatform', 'create:CloudPlatform', 'retrieve:CloudPlatform',
    'update:CloudPlatform', 'destroy:CloudPlatform',
    'list:Company', 'create:Company', 'retrieve:Company',
    'update:Company', 'destroy:Company'
]
deleted = Menu.objects.filter(name__in=old).delete()
print(f'清理孤儿权限: {deleted[0]} 条')
"
```

## 约定总结

### 权限命名规范

```
权限名 = {action}:{菜单name}
菜单 name = 组件 name（defineOptions）= 路由 name（Vue Router）
```

- **action 列表**（`getDefaultAuths` 固定）：`list`、`create`、`update`、`upload`、`destroy`、`retrieve`、`exportData`、`importData`、`batchDestroy`、`partialUpdate`
- **目录节点**（menu_type=0）：`component` 为空字符串 `""`，不参与权限匹配
- **菜单节点**（menu_type=1）：`component` 为组件路径，`name` 同时作为路由名和权限后缀
- **权限节点**（menu_type=2）：`component` 为 `null`，`name` 格式为 `{action}:{菜单name}`

### keep-alive 约束

`<keep-alive :include="cachePageList">` 的 `include` 列表存储路由名，而 Vue 的 keep-alive 匹配的是**组件名**。因此组件名必须与路由名一致，否则缓存失效。这要求权限后缀也必须与两者一致，不能单独修改组件名。

### 凭据权限统一

凭据（Credential）权限同样使用 `destroy:Credential`（非 `delete:`），与平台、公司权限保持一致。`hook.tsx` 中通过 `hasAuth("destroy:Credential")` 显式调用，所有权限的删除动作统一为 `destroy`。
