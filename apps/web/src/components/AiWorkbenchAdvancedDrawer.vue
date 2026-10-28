<script setup lang="ts">
import { ref } from "vue";
import SidebarIcon from "./SidebarIcon.vue";

const props = defineProps<{
  creationMode: "image_generate" | "image_edit";
  denoisingStrength: number | null;
  negativePrompt: string;
  generateCount: number;
  seed: number | null;
}>();

const emit = defineEmits<{
  (e: "update:denoisingStrength", val: number | null): void;
  (e: "update:negativePrompt", val: string): void;
  (e: "update:generateCount", val: number): void;
  (e: "update:seed", val: number | null): void;
}>();

const showAdvanced = ref(false);
</script>

<template>
  <div class="border-t border-line/60 pt-3">
    <button
      type="button"
      class="flex items-center gap-1.5 text-xs font-medium text-muted hover:text-ink transition"
      @click="showAdvanced = !showAdvanced"
    >
      <SidebarIcon
        name="chevron-right"
        class="h-3.5 w-3.5 transition-transform"
        :class="showAdvanced ? 'rotate-90' : ''"
      />
      <span>高级生成选项 (负向词、数量、重绘强度、种子)</span>
    </button>

    <div v-show="showAdvanced" class="mt-3 space-y-3 pl-4">
      <!-- 重绘强度（仅图生图/编辑可见） -->
      <div v-if="creationMode === 'image_edit'">
        <label class="block text-xs font-medium text-muted pb-1">
          重绘/参考强度 (Denoising Strength): {{ denoisingStrength }}
        </label>
        <input
          :value="denoisingStrength"
          type="range"
          min="0.1"
          max="1.0"
          step="0.05"
          class="h-2 w-full cursor-pointer accent-accent"
          @input="emit('update:denoisingStrength', Number(($event.target as HTMLInputElement).value))"
        />
        <div class="flex justify-between text-[10px] text-muted">
          <span>0.1 (微弱重绘，严格保留原图)</span>
          <span>1.0 (大幅重绘，仅参考构图)</span>
        </div>
      </div>

      <!-- 负向提示词 -->
      <div>
        <label class="block text-xs font-medium text-muted pb-1">负向提示词 (Negative Prompt)</label>
        <input
          :value="negativePrompt"
          type="text"
          placeholder="不希望出现在画面中的元素，如：blurry, low quality, bad anatomy, distorted…"
          class="w-full rounded-xl border border-line bg-canvas/20 px-3 py-2 text-xs text-ink outline-none transition placeholder:text-muted/50 focus:border-accent focus:bg-white"
          @input="emit('update:negativePrompt', ($event.target as HTMLInputElement).value)"
        />
      </div>

      <!-- 数量与随机种子 -->
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-muted pb-1">生成张数</label>
          <div class="flex gap-1.5">
            <button
              v-for="n in [1, 2, 4]"
              :key="n"
              type="button"
              class="flex-1 rounded-lg border py-1 text-xs font-medium transition"
              :class="generateCount === n ? 'border-accent bg-accent/10 text-accent font-semibold' : 'border-line bg-white text-ink'"
              @click="emit('update:generateCount', n)"
            >
              {{ n }} 张
            </button>
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-muted pb-1">随机种子 (可选)</label>
          <input
            :value="seed ?? ''"
            type="number"
            placeholder="默认留空随机"
            class="h-8 w-full rounded-lg border border-line bg-canvas/20 px-2.5 text-xs text-ink outline-none transition focus:border-accent focus:bg-white"
            @input="emit('update:seed', ($event.target as HTMLInputElement).value ? Number(($event.target as HTMLInputElement).value) : null)"
          />
        </div>
      </div>
    </div>
  </div>
</template>
