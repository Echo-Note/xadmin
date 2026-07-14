<script lang="ts" setup>
import { useI18n } from "vue-i18n";
import ExpandIcon from "../svg/expand.svg?component";
import UnExpandIcon from "../svg/unexpand.svg?component";
import { useRenderIcon } from "@/components/ReIcon/src/hooks";
import More2Fill from "~icons/ri/more-2-fill?width=18&height=18";
import { computed, getCurrentInstance, nextTick, ref, watch } from "vue";

interface Tree {
  id: number;
  name: string;
  highlight?: boolean;
  children?: Tree[];
}

const props = defineProps({
  treeLoading: Boolean,
  treeData: Array,
  pk: String
});

const emit = defineEmits(["tree-select"]);

const treeRef = ref();
const isExpand = ref(true);
const searchValue = ref("");
const highlightMap = ref({});
const { proxy } = getCurrentInstance();
const defaultProps = {
  children: "children",
  label: "name"
};
const buttonClass = computed(() => {
  return [
    "h-[20px]!",
    "text-sm!",
    "reset-margin",
    "text-(--el-text-color-regular)!",
    "dark:text-white!",
    "dark:hover:text-primary!"
  ];
});

const filterNode = (value: string, data: Tree) => {
  if (!value) return true;
  return data.name.includes(value);
};

function nodeClick(value) {
  const nodeId = value.pk;
  highlightMap.value[nodeId] = highlightMap.value[nodeId]?.highlight
    ? Object.assign({ id: nodeId }, highlightMap.value[nodeId], {
        highlight: false
      })
    : Object.assign({ id: nodeId }, highlightMap.value[nodeId], {
        highlight: true
      });
  Object.values(highlightMap.value).forEach((v: Tree) => {
    if (v.id !== nodeId) {
      v.highlight = false;
    }
  });
  emit(
    "tree-select",
    highlightMap.value[nodeId]?.highlight
      ? Object.assign({ ...value, selected: true })
      : Object.assign({ ...value, selected: false })
  );
}

function toggleRowExpansionAll(status) {
  isExpand.value = status;
  const nodes = (proxy.$refs["treeRef"] as any).store._getAllNodes();
  for (let i = 0; i < nodes.length; i++) {
    nodes[i].expanded = status;
  }
}

/** 重置部门树状态（选中状态、搜索框值、树初始化） */
function onTreeReset() {
  highlightMap.value = {};
  searchValue.value = "";
  toggleRowExpansionAll(true);
}

const { t } = useI18n();

watch(searchValue, val => {
  treeRef.value!.filter(val);
});
watch(
  () => props.pk,
  () => {
    nextTick(() => {
      if (props.pk) {
        highlightMap.value[props.pk] = { highlight: true };
      }
    });
  }
);

defineExpose({ onTreeReset });
</script>

<template>
  <div
    v-loading="props.treeLoading"
    :style="{ minHeight: `calc(100vh - 141px)` }"
    class="dept-tree bg-bg_color overflow-hidden relative"
  >
    <!-- 顶部工具栏：标题 + 搜索 + 操作 -->
    <div class="dept-tree__header">
      <div class="dept-tree__title">
        <IconifyIconOffline icon="ri/organization-chart" class="dept-tree__title-icon" />
        <span class="dept-tree__title-text">{{ t("systemDept.dept") }}</span>
      </div>
      <div class="dept-tree__tools">
        <el-input
          v-model="searchValue"
          :placeholder="t('systemDept.name')"
          class="dept-tree__search"
          clearable
          size="small"
        >
          <template #suffix>
            <el-icon class="el-input__icon">
              <IconifyIconOffline
                v-show="searchValue.length === 0"
                icon="ri/search-line"
              />
            </el-icon>
          </template>
        </el-input>
        <el-dropdown :hide-on-click="false" placement="bottom-end">
          <IconifyIconOffline
            :icon="More2Fill"
            class="dept-tree__more"
            width="18px"
          />
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item>
                <el-button
                  :class="buttonClass"
                  :icon="useRenderIcon(isExpand ? ExpandIcon : UnExpandIcon)"
                  link
                  type="primary"
                  @click="toggleRowExpansionAll(!isExpand)"
                >
                  {{
                    isExpand
                      ? t("buttons.collapseAll")
                      : t("buttons.expendAll")
                  }}
                </el-button>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <el-scrollbar height="calc(100vh - 210px)">
      <el-tree
        ref="treeRef"
        :data="props.treeData"
        :expand-on-click-node="false"
        :filter-node-method="filterNode"
        :props="defaultProps"
        default-expand-all
        node-key="pk"
        @node-click="nodeClick"
      >
        <template #default="{ node, data }">
          <span
            :class="[
              'dept-node',
              'flex',
              'items-center',
              'select-none',
              'truncate',
              searchValue.trim().length > 0 &&
                node.label.includes(searchValue) &&
                'is-match',
              highlightMap[data.pk]?.highlight ? 'is-active' : ''
            ]"
          >
            <span
              :class="[
                'dept-node__label',
                data.children?.length ? 'is-folder' : 'is-leaf'
              ]"
            >
              <IconifyIconOffline
                v-if="data.children?.length"
                icon="ri/folder-3-line"
                class="dept-node__icon"
              />
              <IconifyIconOffline
                v-else
                icon="ri/branch-line"
                class="dept-node__icon"
              />
              <span class="dept-node__text">{{ node.label }}</span>
            </span>
            <el-tag
              v-if="data.user_count"
              size="small"
              round
              effect="plain"
              class="dept-node__count"
            >
              {{ data.user_count }}
            </el-tag>
          </span>
        </template>
      </el-tree>
    </el-scrollbar>
  </div>
</template>

<style lang="scss" scoped>
.dept-tree {
  border-radius: 8px;
}

.dept-tree__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 40px;
  padding: 0 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}

.dept-tree__title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.dept-tree__title-icon {
  width: 18px;
  height: 18px;
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.dept-tree__title-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dept-tree__tools {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  justify-content: flex-end;
  min-width: 0;
}

.dept-tree__search {
  max-width: 160px;
}

.dept-tree__more {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition:
    background-color 0.2s,
    color 0.2s;

  &:hover {
    background-color: var(--el-fill-color);
    color: var(--el-color-primary);
  }
}

:deep(.el-tree) {
  --el-tree-node-hover-bg-color: transparent;
  padding: 8px 6px;
}

:deep(.el-tree-node__content) {
  height: 34px;
  border-radius: 6px;
  padding-right: 8px;
  transition: background-color 0.2s ease;

  &:hover {
    background-color: var(--el-fill-color-light);
  }
}

.dept-node {
  flex: 1;
  min-width: 0;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 6px;
  transition:
    background-color 0.25s ease,
    color 0.25s ease;
}

.dept-node__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
  overflow: hidden;
}

.dept-node__icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

.dept-node__text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.is-folder .dept-node__icon {
  color: var(--el-color-warning);
}

.is-leaf .dept-node__icon {
  color: var(--el-color-success);
}

.dept-node__count {
  flex-shrink: 0;
  height: 18px;
  padding: 0 6px;
  font-size: 12px;
  line-height: 16px;
}

/* 搜索匹配高亮：使用柔和的警告色而非刺眼的红色 */
.is-match .dept-node__text {
  color: var(--el-color-danger);
  font-weight: 500;
}

/* 选中态：左侧主色条 + 浅色背景 + 主色文字 */
.is-active {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
  position: relative;

  &::before {
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 3px;
    height: 60%;
    border-radius: 2px;
    background-color: var(--el-color-primary);
  }

  .dept-node__icon {
    color: var(--el-color-primary) !important;
  }
}

/* 暗色模式适配 */
.dark {
  .dept-tree__header {
    background-color: var(--el-bg-color-overlay);
  }

  .is-active {
    background-color: rgb(64 145 247 / 12%);
    color: var(--el-color-primary);
  }

  :deep(.el-tree-node__content:hover) {
    background-color: rgb(255 255 255 / 6%);
  }
}
</style>
