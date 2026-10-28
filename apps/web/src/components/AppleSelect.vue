<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import SidebarIcon from "./SidebarIcon.vue";

export interface AppleSelectOption {
  value: string | number;
  label: string;
  subLabel?: string;
  badge?: string;
  badgeColor?: "accent" | "emerald" | "amber" | "zinc" | "blue" | "rose";
  disabled?: boolean;
}

const props = withDefaults(
  defineProps<{
    modelValue?: string | number | null;
    options: (AppleSelectOption | string | number)[];
    placeholder?: string;
    searchable?: boolean;
    searchPlaceholder?: string;
    disabled?: boolean;
    mono?: boolean;
    size?: "sm" | "md";
    allowClear?: boolean;
    emptyText?: string;
    dropdownClass?: string;
  }>(),
  {
    modelValue: undefined,
    placeholder: "请选择…",
    searchable: undefined,
    searchPlaceholder: "搜索选项或关键字…",
    disabled: false,
    mono: false,
    size: "md",
    allowClear: false,
    emptyText: "未找到匹配项",
    dropdownClass: ""
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", val: any): void;
  (e: "change", val: any): void;
}>();

const isOpen = ref(false);
const searchQuery = ref("");
const activeIndex = ref(-1);
const openUpward = ref(false);

const containerRef = ref<HTMLElement | null>(null);
const triggerRef = ref<HTMLButtonElement | null>(null);
const searchInputRef = ref<HTMLInputElement | null>(null);
const listboxRef = ref<HTMLElement | null>(null);

// 格式化为标准 Option 对象
const normalizedOptions = computed<AppleSelectOption[]>(() => {
  return props.options.map((item) => {
    if (typeof item === "object" && item !== null) {
      return item as AppleSelectOption;
    }
    return {
      value: item,
      label: String(item)
    };
  });
});

// 自动检测是否需要开启搜索栏（当显式指定或选项总数 > 6 时开启）
const isSearchable = computed(() => {
  if (props.searchable !== undefined) {
    return props.searchable;
  }
  return normalizedOptions.value.length > 6;
});

// 搜索过滤后的可用选项
const filteredOptions = computed<AppleSelectOption[]>(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) {
    return normalizedOptions.value;
  }
  return normalizedOptions.value.filter((opt) => {
    const matchLabel = opt.label.toLowerCase().includes(q);
    const matchVal = String(opt.value).toLowerCase().includes(q);
    const matchSub = opt.subLabel ? opt.subLabel.toLowerCase().includes(q) : false;
    const matchBadge = opt.badge ? opt.badge.toLowerCase().includes(q) : false;
    return matchLabel || matchVal || matchSub || matchBadge;
  });
});

// 当前选中的 Option
const selectedOption = computed<AppleSelectOption | undefined>(() => {
  return normalizedOptions.value.find((opt) => opt.value === props.modelValue);
});

function calculatePlacement(): void {
  if (!triggerRef.value) return;
  const rect = triggerRef.value.getBoundingClientRect();
  const spaceBelow = window.innerHeight - rect.bottom;
  const spaceAbove = rect.top;
  // 若下方空间不足 260px 且上方空间更充裕，则向上弹出
  openUpward.value = spaceBelow < 260 && spaceAbove > spaceBelow;
}

function toggleDropdown(): void {
  if (props.disabled) return;
  if (!isOpen.value) {
    calculatePlacement();
    isOpen.value = true;
    searchQuery.value = "";
    activeIndex.value = filteredOptions.value.findIndex((o) => o.value === props.modelValue);
    if (isSearchable.value) {
      void nextTick(() => {
        searchInputRef.value?.focus();
      });
    }
  } else {
    closeDropdown();
  }
}

function closeDropdown(): void {
  isOpen.value = false;
  searchQuery.value = "";
  activeIndex.value = -1;
}

function selectOption(opt: AppleSelectOption): void {
  if (opt.disabled) return;
  emit("update:modelValue", opt.value);
  emit("change", opt.value);
  closeDropdown();
  triggerRef.value?.focus();
}

function handleClear(e: Event): void {
  e.stopPropagation();
  emit("update:modelValue", null);
  emit("change", null);
}

function onKeyDown(e: KeyboardEvent): void {
  if (props.disabled) return;

  if (!isOpen.value) {
    if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(e.key)) {
      e.preventDefault();
      toggleDropdown();
    }
    return;
  }

  const items = filteredOptions.value;
  if (items.length === 0) {
    if (e.key === "Escape") {
      e.preventDefault();
      closeDropdown();
    }
    return;
  }

  if (e.key === "ArrowDown") {
    e.preventDefault();
    activeIndex.value = (activeIndex.value + 1) % items.length;
    scrollActiveIntoView();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    activeIndex.value = (activeIndex.value - 1 + items.length) % items.length;
    scrollActiveIntoView();
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (activeIndex.value >= 0 && activeIndex.value < items.length) {
      selectOption(items[activeIndex.value]!);
    }
  } else if (e.key === "Escape") {
    e.preventDefault();
    closeDropdown();
    triggerRef.value?.focus();
  }
}

function scrollActiveIntoView(): void {
  void nextTick(() => {
    if (!listboxRef.value) return;
    const activeEl = listboxRef.value.children[activeIndex.value] as HTMLElement | undefined;
    if (activeEl) {
      activeEl.scrollIntoView({ block: "nearest" });
    }
  });
}

function onWindowPointerDown(e: MouseEvent | PointerEvent): void {
  if (!isOpen.value) return;
  const target = e.target as Node | null;
  if (containerRef.value && !containerRef.value.contains(target)) {
    closeDropdown();
  }
}

watch(isOpen, (open) => {
  if (open) {
    window.addEventListener("pointerdown", onWindowPointerDown);
  } else {
    window.removeEventListener("pointerdown", onWindowPointerDown);
  }
});

onUnmounted(() => {
  window.removeEventListener("pointerdown", onWindowPointerDown);
});
</script>

<template>
  <div
    ref="containerRef"
    class="relative w-full"
    @keydown="onKeyDown"
  >
    <!-- 触发器按钮 (Apple HIG 触觉反馈 & 材质层级) -->
    <button
      ref="triggerRef"
      type="button"
      :disabled="disabled"
      class="group flex w-full items-center justify-between gap-2 border bg-white/95 text-left text-ink transition-all duration-150 outline-none select-none active:scale-[0.99] disabled:cursor-not-allowed disabled:bg-canvas/50 disabled:text-muted disabled:border-line/60"
      :class="[
        size === 'sm' ? 'rounded-lg px-2.5 py-1 text-xs' : 'rounded-xl px-3 py-1.5 text-xs',
        isOpen ? 'border-accent ring-2 ring-accent/15' : 'border-line/80 hover:border-line',
        mono ? 'font-mono' : ''
      ]"
      :title="selectedOption ? (selectedOption.subLabel && selectedOption.subLabel !== selectedOption.label ? `${selectedOption.label} (${selectedOption.subLabel})` : selectedOption.label) : placeholder"
      @click="toggleDropdown"
    >
      <div class="min-w-0 flex-1 flex items-center gap-1.5 overflow-hidden">
        <!-- 占位符或已选内容 -->
        <span
          v-if="!selectedOption"
          class="truncate text-muted/70"
        >
          {{ placeholder }}
        </span>
        <template v-else>
          <span class="truncate font-medium text-ink" :title="selectedOption.label">{{ selectedOption.label }}</span>
          <span
            v-if="selectedOption.subLabel && selectedOption.subLabel !== selectedOption.label"
            class="hidden sm:inline font-mono text-[10.5px] text-muted truncate shrink-0 max-w-[48%]"
            :title="selectedOption.subLabel"
          >
            ({{ selectedOption.subLabel }})
          </span>
          <span
            v-if="selectedOption.badge"
            class="ml-auto shrink-0 rounded px-1.5 py-0.2 text-[9.5px] font-medium"
            :class="{
              'bg-accent/10 text-accent border border-accent/20': selectedOption.badgeColor === 'accent',
              'bg-emerald-50 text-emerald-700 border border-emerald-200/60': selectedOption.badgeColor === 'emerald',
              'bg-amber-50 text-amber-700 border border-amber-200/60': selectedOption.badgeColor === 'amber',
              'bg-blue-50 text-blue-700 border border-blue-200/60': selectedOption.badgeColor === 'blue',
              'bg-rose-50 text-rose-700 border border-rose-200/60': selectedOption.badgeColor === 'rose',
              'bg-zinc-100 text-zinc-600 border border-zinc-200/60': !selectedOption.badgeColor || selectedOption.badgeColor === 'zinc'
            }"
          >
            {{ selectedOption.badge }}
          </span>
        </template>
      </div>

      <div class="flex shrink-0 items-center gap-1 pl-1">
        <!-- 清空按钮 -->
        <button
          v-if="allowClear && selectedOption && !disabled"
          type="button"
          class="rounded p-0.5 text-muted hover:bg-canvas hover:text-ink transition"
          title="清空选择"
          @click="handleClear"
        >
          <SidebarIcon name="close" class="h-3 w-3" />
        </button>

        <!-- 顺滑旋转指示箭头 -->
        <SidebarIcon
          name="chevron-right"
          class="h-3.5 w-3.5 text-muted/60 transition-transform duration-200"
          :class="isOpen ? '-rotate-90 text-accent' : 'rotate-90 group-hover:text-ink/80'"
        />
      </div>
    </button>

    <!-- 浮层下拉菜单 (Apple HIG 材质：毛玻璃 backdrop-blur-xl、轻薄阴影与圆角) -->
    <Transition
      enter-active-class="transition duration-150 cubic-bezier(0.16, 1, 0.3, 1)"
      enter-from-class="opacity-0 scale-95 -translate-y-1"
      enter-to-class="opacity-100 scale-100 translate-y-0"
      leave-active-class="transition duration-100 ease-in"
      leave-from-class="opacity-100 scale-100 translate-y-0"
      leave-to-class="opacity-0 scale-95 -translate-y-1"
    >
      <div
        v-if="isOpen"
        class="absolute left-0 right-0 z-50 overflow-hidden rounded-xl border border-line/90 bg-white/95 p-1.5 shadow-2xl backdrop-blur-xl ring-1 ring-black/5"
        :class="[
          openUpward ? 'bottom-full mb-1.5 origin-bottom' : 'top-full mt-1.5 origin-top',
          dropdownClass
        ]"
      >
        <!-- 搜索过滤条 (当选项多时启用 Spotlight 级过滤体验) -->
        <div v-if="isSearchable" class="relative mb-1 px-0.5">
          <div class="relative flex items-center">
            <SidebarIcon
              name="search"
              class="pointer-events-none absolute left-2.5 h-3.5 w-3.5 text-muted/60"
            />
            <input
              ref="searchInputRef"
              v-model="searchQuery"
              type="text"
              :placeholder="searchPlaceholder"
              class="w-full rounded-lg border border-line/70 bg-canvas/60 py-1.5 pl-8 pr-7 text-xs text-ink outline-none transition placeholder:text-muted/60 focus:border-accent focus:bg-white focus:ring-1 focus:ring-accent/20"
              @keydown.stop="onKeyDown"
            />
            <button
              v-if="searchQuery"
              type="button"
              class="absolute right-2 p-0.5 text-muted/50 hover:text-ink transition"
              title="清空搜索"
              @click="searchQuery = ''; searchInputRef?.focus()"
            >
              <SidebarIcon name="close" class="h-3 w-3" />
            </button>
          </div>
        </div>

        <!-- 选项列表区 -->
        <div
          ref="listboxRef"
          class="max-h-56 overflow-y-auto space-y-0.5 p-0.5 select-none"
        >
          <div
            v-if="filteredOptions.length === 0"
            class="py-4 text-center text-xs text-muted"
          >
            {{ emptyText }}
          </div>

          <button
            v-for="(opt, idx) in filteredOptions"
            :key="opt.value"
            type="button"
            :disabled="opt.disabled"
            class="group flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs transition-colors duration-100"
            :class="[
              opt.disabled ? 'cursor-not-allowed opacity-40' : 'cursor-pointer',
              opt.value === modelValue
                ? 'bg-accent/10 text-accent font-medium'
                : idx === activeIndex
                  ? 'bg-canvas text-ink'
                  : 'text-ink/90 hover:bg-canvas/80 hover:text-ink'
            ]"
            @click="selectOption(opt)"
            @mouseenter="activeIndex = idx"
          >
            <div class="min-w-0 flex-1 pr-2">
              <div class="flex items-center gap-1.5">
                <span :class="mono ? 'font-mono' : ''" class="truncate font-medium" :title="opt.label">{{ opt.label }}</span>
                <span
                  v-if="opt.badge"
                  class="shrink-0 rounded px-1.5 py-0.2 text-[9.5px] font-medium"
                  :class="{
                    'bg-accent/15 text-accent': opt.badgeColor === 'accent',
                    'bg-emerald-50 text-emerald-700': opt.badgeColor === 'emerald',
                    'bg-amber-50 text-amber-700': opt.badgeColor === 'amber',
                    'bg-blue-50 text-blue-700': opt.badgeColor === 'blue',
                    'bg-rose-50 text-rose-700': opt.badgeColor === 'rose',
                    'bg-zinc-100 text-zinc-600': !opt.badgeColor || opt.badgeColor === 'zinc'
                  }"
                >
                  {{ opt.badge }}
                </span>
              </div>
              <p
                v-if="opt.subLabel && opt.subLabel !== opt.label"
                class="font-mono text-[10.5px] text-muted truncate mt-0.5"
                :title="opt.subLabel"
              >
                {{ opt.subLabel }}
              </p>
            </div>

            <!-- Apple HIG 选中态 Checkmark -->
            <SidebarIcon
              v-if="opt.value === modelValue"
              name="check"
              class="h-3.5 w-3.5 shrink-0 text-accent"
            />
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
