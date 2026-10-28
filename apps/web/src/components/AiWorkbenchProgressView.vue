<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import SidebarIcon from "./SidebarIcon.vue";

const props = defineProps<{
  prompt: string;
  modelName?: string;
  aspectRatio?: string;
  size?: string;
  progressPct?: number | null;
  cancelling?: boolean;
}>();

const emit = defineEmits<{
  (e: "cancel"): void;
  (e: "background-run"): void;
}>();

const elapsedSeconds = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  timer = setInterval(() => {
    elapsedSeconds.value += 1;
  }, 1000);
});

onUnmounted(() => {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
});

const formattedTime = computed(() => {
  const m = Math.floor(elapsedSeconds.value / 60);
  const s = elapsedSeconds.value % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
});

const stageText = computed(() => {
  const s = elapsedSeconds.value;
  if (s < 3) return "正在连接生图模型推理节点…";
  if (s < 8) return "正在构建画面主体构图与光影景深…";
  if (s < 15) return "正在高精渲染表面细节、材质与微观质感…";
  return "正在执行色彩平衡校正与高保真编码输出…";
});

const stageBadge = computed(() => {
  const s = elapsedSeconds.value;
  if (s < 3) return "准备环境";
  if (s < 8) return "艺术构图";
  if (s < 15) return "精细渲染";
  return "色彩校准";
});

const displayRatioClass = computed(() => {
  const ar = props.aspectRatio;
  if (ar === "16:9") return "aspect-video max-w-lg";
  if (ar === "9:16") return "aspect-[9/16] max-h-[380px] w-auto";
  if (ar === "4:3") return "aspect-[4/3] max-w-md";
  if (ar === "3:4") return "aspect-[3/4] max-h-[380px] w-auto";
  return "aspect-square max-w-[340px]";
});
</script>

<template>
  <div class="flex flex-col items-center justify-center py-6 px-4">
    <!-- 主视觉流动光感画板 (ChatGPT / Fluid Living Material) -->
    <div
      class="relative flex w-full flex-col items-center justify-center overflow-hidden rounded-2xl border border-line/60 bg-zinc-900/95 shadow-2xl transition-all"
      :class="displayRatioClass"
    >
      <!-- 柔和环境光晕 (Ambient Glow Mesh) -->
      <div
        class="pointer-events-none absolute -top-12 -left-12 h-44 w-44 rounded-full bg-blue-500/20 blur-3xl transition duration-1000 animate-pulse"
      />
      <div
        class="pointer-events-none absolute -bottom-12 -right-12 h-48 w-48 rounded-full bg-indigo-500/20 blur-3xl transition duration-1000"
      />

      <!-- 流动光波扫过 (Shimmer Sweep) -->
      <div class="pointer-events-none absolute inset-0 shimmer-wave" />

      <!-- 中心同心扩散涟漪微动效 -->
      <div class="relative z-10 flex flex-col items-center gap-3 p-6 text-center">
        <div class="relative flex h-14 w-14 items-center justify-center">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400/25 opacity-75" />
          <span class="absolute inline-flex h-11 w-11 rounded-full bg-blue-500/20 backdrop-blur-md" />
          <div class="relative flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-tr from-blue-600 to-indigo-500 text-white shadow-lg">
            <SidebarIcon name="star" class="h-4 w-4 animate-spin [animation-duration:6s]" />
          </div>
        </div>

        <div>
          <div class="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] font-medium text-blue-200 backdrop-blur-md">
            <span class="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
            <span>{{ stageBadge }}</span>
            <span class="text-white/40">·</span>
            <span class="font-mono">{{ formattedTime }}</span>
          </div>

          <p class="mt-2 text-xs font-medium text-white/90 tracking-wide">
            {{ stageText }}
          </p>
        </div>

        <!-- 规格信息徽标 -->
        <div class="flex items-center gap-2 text-[10.5px] text-white/50">
          <span v-if="modelName" class="rounded bg-white/10 px-1.5 py-0.5 font-medium text-white/70">
            {{ modelName }}
          </span>
          <span v-if="aspectRatio" class="font-mono">{{ aspectRatio }}</span>
          <span v-if="size" class="font-mono text-white/40">({{ size }})</span>
        </div>
      </div>
    </div>

    <!-- 正在创作的提示词微缩摘要 -->
    <div class="mt-4 w-full max-w-lg rounded-xl border border-line/70 bg-canvas/60 p-3 text-xs leading-relaxed text-ink/80 backdrop-blur-sm">
      <div class="flex items-center justify-between pb-1 text-[11px] font-semibold text-muted">
        <span>当前创作提示词</span>
        <span class="text-[10px] text-muted/60 font-mono">{{ prompt.length }} 字符</span>
      </div>
      <p class="line-clamp-2 italic text-ink/90">
        “{{ prompt }}”
      </p>
    </div>

    <!-- 底部控制按钮：后台运行 vs 取消生成 -->
    <div class="mt-5 flex items-center justify-center gap-3">
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-line bg-white px-3.5 py-2 text-xs font-medium text-ink transition hover:bg-canvas active:scale-97"
        @click="emit('background-run')"
      >
        <SidebarIcon name="clock" class="h-3.5 w-3.5 text-muted" />
        <span>放入后台运行 (Esc)</span>
      </button>

      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50/80 px-3.5 py-2 text-xs font-medium text-rose-700 transition hover:bg-rose-100 active:scale-97 disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="cancelling"
        @click="emit('cancel')"
      >
        <SidebarIcon name="close" class="h-3.5 w-3.5" />
        <span>{{ cancelling ? "正在取消…" : "中止本次生成" }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.shimmer-wave {
  background: linear-gradient(
    115deg,
    transparent 0%,
    rgba(255, 255, 255, 0.03) 40%,
    rgba(255, 255, 255, 0.12) 50%,
    rgba(255, 255, 255, 0.03) 60%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmerMove 3.5s infinite ease-in-out;
}

@keyframes shimmerMove {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .shimmer-wave {
    animation: none;
  }
}
</style>
