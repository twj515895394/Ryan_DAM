<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from "vue";

import { library, dismissImportJob, retryFailedImports, forceImportSkipped } from "../stores/library";

/** 导入结束后面板自动关闭的等待时长（毫秒）。 */
const AUTO_DISMISS_MS = 5000;

const job = computed(() => library.importJob);

const processed = computed(() =>
  job.value ? job.value.success_count + job.value.skipped_count + job.value.failed_count : 0
);

const percent = computed(() => {
  if (!job.value || job.value.total_count === 0) return 0;
  return Math.round((processed.value / job.value.total_count) * 100);
});

const statusLabel = computed(() => {
  switch (job.value?.status) {
    case "queued": return "排队中";
    case "running": return "正在导入";
    case "completed": return "导入完成";
    case "completed_with_errors": return "完成（有失败项）";
    case "failed": return "导入失败";
    case "interrupted": return "已中断";
    default: return "";
  }
});

const done = computed(() => job.value !== null && !["queued", "running"].includes(job.value.status));

let autoDismissTimer: ReturnType<typeof setTimeout> | null = null;

// 完成态出现后 5 秒自动关闭；重试/强制导入等使任务重新进入运行态时撤销计时
watch(done, (isDone) => {
  if (autoDismissTimer !== null) {
    clearTimeout(autoDismissTimer);
    autoDismissTimer = null;
  }
  if (isDone) autoDismissTimer = setTimeout(dismissImportJob, AUTO_DISMISS_MS);
});

onBeforeUnmount(() => {
  if (autoDismissTimer !== null) clearTimeout(autoDismissTimer);
});
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-150"
      enter-from-class="opacity-0 translate-y-2"
      leave-active-class="transition duration-150"
      leave-to-class="opacity-0 translate-y-2"
    >
      <div v-if="job" class="fixed bottom-5 right-5 z-40 w-80 rounded-2xl border border-line bg-white p-4 shadow-soft">
        <div class="flex items-center justify-between">
          <p class="text-sm font-semibold">导入任务</p>
          <span
            class="text-xs font-medium"
            :class="job.status === 'failed' || job.status === 'completed_with_errors' ? 'text-rose-700' : done ? 'text-emerald-700' : 'text-muted'"
          >{{ statusLabel }}</span>
        </div>

        <div class="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-canvas">
          <div
            class="h-full rounded-full transition-all duration-300"
            :class="job.status === 'failed' ? 'bg-rose-500' : 'bg-accent'"
            :style="{ width: `${percent}%` }"
          />
        </div>
        <p class="mt-1.5 text-xs text-muted">{{ processed }} / {{ job.total_count }} 项 · {{ percent }}%</p>

        <div class="mt-2 flex gap-3 text-xs">
          <span class="text-emerald-700">成功 {{ job.success_count }}</span>
          <span class="text-amber-700">跳过 {{ job.skipped_count }}</span>
          <span class="text-rose-700">失败 {{ job.failed_count }}</span>
        </div>

        <p v-if="job.message" class="mt-2 rounded-lg bg-rose-50 px-2.5 py-1.5 text-xs leading-5 text-rose-700">
          {{ job.message }}
        </p>

        <ul v-if="done && job.failed_count > 0" class="mt-2 max-h-32 space-y-1 overflow-y-auto">
          <li v-for="item in job.items.filter((i) => i.status === 'failed')" :key="item.id" class="text-xs leading-5 text-muted">
            <span class="text-rose-600">✕</span> {{ item.source_path.split(/[\\/]/).pop() }} — {{ item.error_message }}
          </li>
        </ul>

        <div class="mt-3 flex justify-end gap-1">
          <button
            v-if="done && job.skipped_count > 0"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-amber-700 transition hover:bg-canvas"
            @click="forceImportSkipped"
          >仍要导入重复项</button>
          <button
            v-if="done && job.failed_count > 0"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-canvas"
            @click="retryFailedImports"
          >重试失败项目</button>
          <button
            v-if="done"
            class="rounded-lg px-3 py-1.5 text-xs font-medium text-accent transition hover:bg-canvas"
            @click="dismissImportJob"
          >关闭</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
