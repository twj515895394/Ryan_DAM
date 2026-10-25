<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import { library } from "../stores/library";

const sortOptions: Array<{
  value: "created_at" | "name" | "size" | "updated_at";
  label: string;
}> = [
  { value: "created_at", label: "最新导入" },
  { value: "name", label: "按文件名" },
  { value: "size", label: "按文件体积" },
  { value: "updated_at", label: "最近修改" }
];

const menuOpen = ref(false);
const controlRef = ref<HTMLElement | null>(null);

const currentLabel = computed(() => {
  const hit = sortOptions.find((opt) => opt.value === library.assetQuery.sort);
  return hit ? hit.label : "最新导入";
});

function toggleOrder(): void {
  library.assetQuery.order = library.assetQuery.order === "desc" ? "asc" : "desc";
}

function selectSort(val: "created_at" | "name" | "size" | "updated_at"): void {
  library.assetQuery.sort = val;
  menuOpen.value = false;
}

function onDocClick(e: MouseEvent): void {
  if (!menuOpen.value) return;
  const target = e.target as HTMLElement | null;
  if (controlRef.value && !controlRef.value.contains(target)) {
    menuOpen.value = false;
  }
}

function onDocKeydown(e: KeyboardEvent): void {
  if (menuOpen.value && e.key === "Escape") {
    menuOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener("mousedown", onDocClick);
  document.addEventListener("keydown", onDocKeydown);
});

onUnmounted(() => {
  document.removeEventListener("mousedown", onDocClick);
  document.removeEventListener("keydown", onDocKeydown);
});
</script>

<template>
  <div ref="controlRef" class="relative inline-flex items-center">
    <!-- Apple HIG 连体式胶囊排序控件 -->
    <div
      class="inline-flex h-9 items-center rounded-xl border border-line bg-white/95 shadow-xs transition hover:border-line/80 hover:bg-canvas/30"
    >
      <!-- 左段：排序维度触发器 -->
      <button
        type="button"
        class="flex h-full items-center gap-1.5 pl-3 pr-2 text-xs font-medium text-ink transition active:scale-97 select-none"
        :title="`排序方式：${currentLabel}`"
        @click="menuOpen = !menuOpen"
      >
        <span>{{ currentLabel }}</span>
        <svg
          class="h-3 w-3 text-muted/80 transition-transform duration-200"
          :class="menuOpen ? 'rotate-180 text-accent' : ''"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fill-rule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clip-rule="evenodd"
          />
        </svg>
      </button>

      <!-- 控件中间微弱分隔线 -->
      <div class="h-4 w-[1px] bg-line/80"></div>

      <!-- 右段：升序/降序切换器（带 180° 平滑翻转动画） -->
      <button
        type="button"
        class="flex h-full w-8 items-center justify-center text-muted transition hover:text-ink active:scale-95"
        :title="library.assetQuery.order === 'desc' ? '当前：降序（点击切换升序）' : '当前：升序（点击切换降序）'"
        @click="toggleOrder"
      >
        <SidebarIcon
          name="arrow-down"
          class="h-3.5 w-3.5 transition-transform duration-300"
          :class="library.assetQuery.order === 'asc' ? '-rotate-180 text-accent' : ''"
        />
      </button>
    </div>

    <!-- 弹出的精致浮层菜单 -->
    <Transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="menuOpen"
        class="absolute left-0 top-11 z-50 w-36 overflow-hidden rounded-xl border border-white/60 bg-white/95 p-1 shadow-xl backdrop-blur-xl ring-1 ring-black/5"
      >
        <button
          v-for="opt in sortOptions"
          :key="opt.value"
          type="button"
          class="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs font-medium transition text-left"
          :class="
            library.assetQuery.sort === opt.value
              ? 'bg-accent/10 text-accent font-semibold'
              : 'text-ink hover:bg-canvas'
          "
          @click="selectSort(opt.value)"
        >
          <span>{{ opt.label }}</span>
          <SidebarIcon
            v-if="library.assetQuery.sort === opt.value"
            name="check"
            class="h-3 w-3 text-accent"
          />
        </button>
      </div>
    </Transition>
  </div>
</template>
