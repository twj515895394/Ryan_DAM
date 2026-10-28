<script setup lang="ts">
import { computed, ref } from "vue";
import { useAiResultImageDetails } from "../composables/useAiResultCache";
import SidebarIcon from "./SidebarIcon.vue";

const props = withDefaults(
  defineProps<{
    resultId: string;
    alt?: string;
    aspectRatio?: string;
    fit?: "cover" | "contain";
    rounded?: string;
    clickable?: boolean;
    hoverZoom?: boolean;
  }>(),
  {
    alt: "AI 生成产物",
    aspectRatio: "",
    fit: "cover",
    rounded: "rounded-lg",
    clickable: false,
    hoverZoom: false
  }
);

const emit = defineEmits<{
  (e: "click", event: MouseEvent): void;
}>();

const { objectUrl, loading, error } = useAiResultImageDetails(() => props.resultId);
const imgDecodeFailed = ref(false);

const fitClass = computed(() => {
  return props.fit === "contain" ? "object-contain" : "object-cover";
});
</script>

<template>
  <div
    class="relative overflow-hidden bg-canvas/60 border border-line/60 flex items-center justify-center shrink-0 select-none group"
    :class="[
      rounded,
      aspectRatio,
      clickable ? 'cursor-pointer hover:border-accent/60 hover:shadow-xs transition' : ''
    ]"
    @click="clickable ? emit('click', $event) : undefined"
  >
    <!-- 图片呈现 -->
    <img
      v-if="objectUrl && !imgDecodeFailed"
      :src="objectUrl"
      :alt="alt"
      loading="lazy"
      class="h-full w-full transition duration-300"
      :class="[
        fitClass,
        hoverZoom ? 'group-hover:scale-104' : ''
      ]"
      @error="imgDecodeFailed = true"
    />

    <!-- 加载骨架态 -->
    <div
      v-else-if="loading"
      class="flex h-full w-full items-center justify-center bg-canvas/40 animate-pulse text-muted"
    >
      <SidebarIcon name="star" class="h-4 w-4 animate-spin opacity-40 text-accent" />
    </div>

    <!-- 空白、加载失败或解码异常降级 -->
    <div
      v-else
      class="flex h-full w-full items-center justify-center bg-canvas/30 text-muted/60"
      :title="error || '无预览缩略图'"
    >
      <SidebarIcon name="image" class="h-4 w-4 opacity-40" />
    </div>

    <!-- 可点击悬浮指示器（如果有需要） -->
    <div
      v-if="clickable"
      class="pointer-events-none absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center"
    >
      <div
        class="opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 backdrop-blur-xs text-white rounded-full p-1 shadow-xs"
      >
        <SidebarIcon name="search" class="h-3 w-3" />
      </div>
    </div>
  </div>
</template>
