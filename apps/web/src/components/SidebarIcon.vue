<script setup lang="ts">
defineProps<{
  name:
    | "grid"
    | "folder"
    | "folder-open"
    | "tag"
    | "project"
    | "external"
    | "trash"
    | "settings"
    | "plus"
    | "chevron-right"
    | "edit"
    | "close"
    | "refresh";
}>();
</script>

<template>
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="shrink-0"
    aria-hidden="true"
  >
    <!-- 全部资产 / 四宫格 -->
    <template v-if="name === 'grid'">
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </template>

    <!-- 闭合文件夹 -->
    <template v-else-if="name === 'folder'">
      <path d="M3.5 6.5A1.5 1.5 0 0 1 5 5h4.2a1.5 1.5 0 0 1 1.1.5L11.8 7H19a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 17.5z" />
    </template>

    <!-- 打开的文件夹 -->
    <template v-else-if="name === 'folder-open'">
      <path d="M4 6.5A1.5 1.5 0 0 1 5.5 5h4a1.5 1.5 0 0 1 1.1.5L12 7h6.5A1.5 1.5 0 0 1 20 8.5v1" />
      <path d="m3.5 18 2.2-7.8A1.5 1.5 0 0 1 7.1 9h14.4a1 1 0 0 1 .9 1.3l-2.4 7.7a1.5 1.5 0 0 1-1.4 1H5a1.5 1.5 0 0 1-1.5-1z" />
    </template>

    <!-- 标签 -->
    <template v-else-if="name === 'tag'">
      <path d="m20 12.5-7.5 7.5a2 2 0 0 1-2.8 0L3.5 13.8a1.5 1.5 0 0 1-.4-1.1V4.5A1.5 1.5 0 0 1 4.6 3h8.2a1.5 1.5 0 0 1 1.1.4L20 9.7a2 2 0 0 1 0 2.8z" />
      <circle cx="8" cy="8" r="1.5" fill="currentColor" />
    </template>

    <!-- 项目（层叠夹/板块） -->
    <template v-else-if="name === 'project'">
      <path d="M4 4.5h16a1.5 1.5 0 0 1 1.5 1.5v12a1.5 1.5 0 0 1-1.5 1.5H4A1.5 1.5 0 0 1 2.5 18V6A1.5 1.5 0 0 1 4 4.5z" />
      <path d="M2.5 9.5h19" />
      <path d="M8 9.5v10" />
    </template>

    <!-- 外部目录 / 磁盘驱动器 -->
    <template v-else-if="name === 'external'">
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
      <path d="M7 15h.01" />
      <path d="M10 15h.01" />
      <path d="M17 12a2 2 0 1 0-4 0 2 2 0 0 0 4 0z" />
    </template>

    <!-- 回收站 / 废纸篓 -->
    <template v-else-if="name === 'trash'">
      <path d="M4.5 6.5h15" />
      <path d="M9.5 6.5V4.8a1.3 1.3 0 0 1 1.3-1.3h2.4a1.3 1.3 0 0 1 1.3 1.3v1.7" />
      <path d="M6 6.5l1 12.2a2 2 0 0 0 2 1.8h6a2 2 0 0 0 2-1.8l1-12.2" />
      <path d="M10 11v5" />
      <path d="M14 11v5" />
    </template>

    <!-- 设置 / 齿轮 -->
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </template>

    <!-- 精细加号 -->
    <template v-else-if="name === 'plus'">
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </template>

    <!-- 右箭头 / 展开折叠三角 -->
    <template v-else-if="name === 'chevron-right'">
      <path d="m9 18 6-6-6-6" />
    </template>

    <!-- 铅笔编辑 -->
    <template v-else-if="name === 'edit'">
      <path d="M17 3a2.8 2.8 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z" />
    </template>

    <!-- 关闭 / 删除叉号 -->
    <template v-else-if="name === 'close'">
      <path d="m18 6-12 12" />
      <path d="m6 6 12 12" />
    </template>

    <!-- 重新扫描 / 刷新 -->
    <template v-else-if="name === 'refresh'">
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 21h5v-5" />
    </template>
  </svg>
</template>
