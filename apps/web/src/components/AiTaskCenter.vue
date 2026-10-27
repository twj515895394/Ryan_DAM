<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import SidebarIcon from "./SidebarIcon.vue";
import { api } from "../api/client";
import type { AiResult, AiTaskDetail, AiTaskStatus, AiTaskSummary, AiTaskType } from "../api/types";

const props = defineProps<{
  open: boolean;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "open-variant", task: AiTaskSummary | AiTaskDetail): void;
  (e: "continue-edit", result: AiResult, task: AiTaskDetail): void;
}>();

const tasks = ref<AiTaskSummary[]>([]);
const totalCount = ref(0);
const loading = ref(false);
const activeFilter = ref<"all" | "active" | "recovery" | "finished">("all");
const selectedTaskDetail = ref<AiTaskDetail | null>(null);
const loadingDetail = ref(false);
const actionTaskId = ref<string | null>(null);

let pollTimer: ReturnType<typeof setInterval> | null = null;

async function loadTasks(silent = false): Promise<void> {
  if (!silent) loading.value = true;
  try {
    const res = await api.listAiTasks({ limit: 50 });
    tasks.value = res.items;
    totalCount.value = res.total;
  } catch (err) {
    console.error("加载 AI 任务列表失败:", err);
  } finally {
    if (!silent) loading.value = false;
  }
}

async function inspectTask(taskId: string): Promise<void> {
  if (selectedTaskDetail.value?.id === taskId) {
    selectedTaskDetail.value = null;
    return;
  }
  loadingDetail.value = true;
  try {
    const detail = await api.getAiTask(taskId);
    selectedTaskDetail.value = detail;
  } catch (err) {
    console.error("加载任务详情失败:", err);
  } finally {
    loadingDetail.value = false;
  }
}

async function handleCancel(taskId: string): Promise<void> {
  actionTaskId.value = taskId;
  try {
    await api.cancelAiTask(taskId);
    await loadTasks(true);
    if (selectedTaskDetail.value?.id === taskId) {
      selectedTaskDetail.value = await api.getAiTask(taskId);
    }
  } catch (err) {
    console.error("取消任务失败:", err);
  } finally {
    actionTaskId.value = null;
  }
}

async function handleRetry(taskId: string): Promise<void> {
  actionTaskId.value = taskId;
  try {
    const newTask = await api.retryAiTask(taskId);
    await loadTasks(true);
    await inspectTask(newTask.id);
  } catch (err) {
    console.error("重试任务失败:", err);
  } finally {
    actionTaskId.value = null;
  }
}

const importingResultId = ref<string | null>(null);

async function handleImportResult(resultId: string): Promise<void> {
  importingResultId.value = resultId;
  try {
    const asset = await api.importAiResultToAsset(resultId);
    if (selectedTaskDetail.value) {
      const res = selectedTaskDetail.value.results.find((r) => r.id === resultId);
      if (res) {
        res.imported_asset_id = asset.id;
      }
    }
  } catch (err) {
    console.error("入库失败:", err);
  } finally {
    importingResultId.value = null;
  }
}

const filteredTasks = computed(() => {
  if (activeFilter.value === "active") {
    return tasks.value.filter((t) => ["queued", "running", "cancel_requested"].includes(t.status));
  }
  if (activeFilter.value === "recovery") {
    return tasks.value.filter((t) => t.status === "recovery_needed");
  }
  if (activeFilter.value === "finished") {
    return tasks.value.filter((t) => ["succeeded", "failed", "partial_failed", "canceled"].includes(t.status));
  }
  return tasks.value;
});

const activeTasksCount = computed(() => {
  return tasks.value.filter((t) => ["queued", "running", "cancel_requested"].includes(t.status)).length;
});

const recoveryCount = computed(() => {
  return tasks.value.filter((t) => t.status === "recovery_needed").length;
});

function taskTypeLabel(type: AiTaskType): string {
  switch (type) {
    case "image_generate": return "文生图";
    case "image_edit": return "图像编辑";
    case "batch_reverse": return "批量反推";
    case "prompt_optimize": return "提示词优化";
    default: return type;
  }
}

function statusBadge(status: AiTaskStatus): { text: string; bg: string; textClass: string; dotClass: string } {
  switch (status) {
    case "queued":
      return { text: "排队中", bg: "bg-slate-100", textClass: "text-slate-700", dotClass: "bg-slate-400" };
    case "running":
      return { text: "执行中", bg: "bg-sky-50", textClass: "text-sky-700", dotClass: "bg-sky-500 animate-pulse" };
    case "succeeded":
      return { text: "已完成", bg: "bg-emerald-50", textClass: "text-emerald-700", dotClass: "bg-emerald-500" };
    case "partial_failed":
      return { text: "部分完成", bg: "bg-amber-50", textClass: "text-amber-800", dotClass: "bg-amber-500" };
    case "failed":
      return { text: "执行失败", bg: "bg-rose-50", textClass: "text-rose-700", dotClass: "bg-rose-500" };
    case "cancel_requested":
      return { text: "正在取消", bg: "bg-amber-50", textClass: "text-amber-700", dotClass: "bg-amber-400 animate-ping" };
    case "canceled":
      return { text: "已取消", bg: "bg-slate-100", textClass: "text-slate-500", dotClass: "bg-slate-300" };
    case "recovery_needed":
      return { text: "待核验状态", bg: "bg-amber-100/80", textClass: "text-amber-900 font-semibold", dotClass: "bg-amber-600" };
    default:
      return { text: status, bg: "bg-slate-100", textClass: "text-slate-600", dotClass: "bg-slate-400" };
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch {
    return iso;
  }
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      loadTasks();
      if (!pollTimer) {
        pollTimer = setInterval(() => loadTasks(true), 3000);
      }
    } else {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    }
  },
  { immediate: true }
);

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex justify-end bg-black/20 backdrop-blur-xs transition-opacity"
      @click.self="emit('close')"
    >
      <div
        class="flex h-full w-[460px] max-w-[90vw] flex-col border-l border-line bg-white/95 shadow-2xl backdrop-blur-xl animate-in slide-in-from-right duration-200"
      >
        <!-- 顶栏标题 -->
        <div class="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div class="flex items-center gap-2">
            <div class="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/10 text-accent">
              <SidebarIcon name="star" class="h-4 w-4" />
            </div>
            <div>
              <h2 class="text-sm font-semibold text-ink">AI 任务中心</h2>
              <p class="text-[10.5px] text-muted">受控并发 · 异步排队 · 状态追踪</p>
            </div>
          </div>
          <button
            type="button"
            class="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-canvas hover:text-ink transition"
            title="关闭 (<kbd>Esc</kbd>)"
            @click="emit('close')"
          >
            <SidebarIcon name="close" class="h-3.5 w-3.5" />
          </button>
        </div>

        <!-- 过滤分段标签 -->
        <div class="flex items-center gap-1 border-b border-line/60 bg-canvas/40 px-4 py-2 text-xs">
          <button
            type="button"
            class="rounded-lg px-2.5 py-1 font-medium transition"
            :class="activeFilter === 'all' ? 'bg-white shadow-2xs text-ink' : 'text-muted hover:text-ink'"
            @click="activeFilter = 'all'"
          >
            全部 ({{ totalCount }})
          </button>
          <button
            type="button"
            class="flex items-center gap-1 rounded-lg px-2.5 py-1 font-medium transition"
            :class="activeFilter === 'active' ? 'bg-white shadow-2xs text-accent font-semibold' : 'text-muted hover:text-ink'"
            @click="activeFilter = 'active'"
          >
            <span>进行中</span>
            <span v-if="activeTasksCount > 0" class="rounded-full bg-accent/15 px-1.5 py-0.2 text-[10px] text-accent">
              {{ activeTasksCount }}
            </span>
          </button>
          <button
            type="button"
            class="flex items-center gap-1 rounded-lg px-2.5 py-1 font-medium transition"
            :class="activeFilter === 'recovery' ? 'bg-white shadow-2xs text-amber-800 font-semibold' : 'text-muted hover:text-ink'"
            @click="activeFilter = 'recovery'"
          >
            <span>待核验</span>
            <span v-if="recoveryCount > 0" class="rounded-full bg-amber-200 px-1.5 py-0.2 text-[10px] text-amber-900">
              {{ recoveryCount }}
            </span>
          </button>
          <button
            type="button"
            class="rounded-lg px-2.5 py-1 font-medium transition"
            :class="activeFilter === 'finished' ? 'bg-white shadow-2xs text-ink' : 'text-muted hover:text-ink'"
            @click="activeFilter = 'finished'"
          >
            历史
          </button>
        </div>

        <!-- 任务列表区域 -->
        <div class="flex-1 overflow-y-auto p-4 space-y-2.5 divide-y divide-line/30">
          <div v-if="loading && tasks.length === 0" class="flex flex-col items-center justify-center py-16 text-muted">
            <SidebarIcon name="star" class="h-6 w-6 animate-spin opacity-40 mb-2" />
            <span class="text-xs">加载任务中…</span>
          </div>

          <div v-else-if="filteredTasks.length === 0" class="flex flex-col items-center justify-center py-16 text-muted">
            <SidebarIcon name="image" class="h-8 w-8 opacity-20 mb-2" />
            <span class="text-xs">当前没有符合条件的 AI 任务</span>
          </div>

          <div
            v-for="task in filteredTasks"
            :key="task.id"
            class="pt-2.5 first:pt-0"
          >
            <div
              class="group relative rounded-xl border border-line/70 bg-white p-3 shadow-2xs transition hover:border-line hover:shadow-xs cursor-pointer"
              :class="selectedTaskDetail?.id === task.id ? 'ring-2 ring-accent/40 border-accent/60' : ''"
              @click="inspectTask(task.id)"
            >
              <!-- 任务类型与状态标签 -->
              <div class="flex items-center justify-between text-xs mb-1.5">
                <div class="flex items-center gap-1.5">
                  <span class="rounded bg-canvas px-1.5 py-0.5 text-[10.5px] font-medium text-ink">
                    {{ taskTypeLabel(task.task_type) }}
                  </span>
                  <span v-if="task.retry_of" class="text-[10px] text-muted">
                    重试自 #{{ task.retry_of.slice(-6) }}
                  </span>
                </div>

                <div
                  class="flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10.5px]"
                  :class="[statusBadge(task.status).bg, statusBadge(task.status).textClass]"
                >
                  <span class="h-1.5 w-1.5 rounded-full" :class="statusBadge(task.status).dotClass" />
                  <span>{{ statusBadge(task.status).text }}</span>
                </div>
              </div>

              <!-- 提示词或描述 -->
              <p class="text-xs text-ink/90 line-clamp-2 leading-relaxed mb-2">
                {{ task.prompt_final || "（无提示词）" }}
              </p>

              <!-- 模型 & Provider -->
              <div class="flex items-center justify-between text-[11px] text-muted">
                <span class="truncate max-w-[240px]">
                  {{ task.model_name || "默认模型" }} · {{ task.provider_name || "本地" }}
                </span>
                <span>{{ formatTime(task.created_at) }}</span>
              </div>

              <!-- 待核验 / 进程中断特殊告警说明 -->
              <div
                v-if="task.status === 'recovery_needed'"
                class="mt-2 rounded-lg bg-amber-50/80 border border-amber-200/60 p-2 text-[11px] text-amber-900 leading-normal"
              >
                ⚠️ <strong>服务曾异常重启：</strong>任务中断且上游计费状态未知，系统已拦截避免盲目重试。核对后可安全重新排队。
              </div>

              <!-- 失败错误详情展示 -->
              <div
                v-else-if="task.status === 'failed' && task.error_message"
                class="mt-2 rounded-lg bg-rose-50/80 border border-rose-200/60 p-2 text-[11px] text-rose-800 leading-normal truncate"
                :title="task.error_message"
              >
                ❌ {{ task.error_message }}
              </div>

              <!-- 快捷操作按钮 -->
              <div class="mt-2.5 flex items-center justify-end gap-1.5 pt-1 border-t border-line/40">
                <button
                  v-if="['queued', 'running'].includes(task.status)"
                  type="button"
                  class="rounded-md border border-line/80 bg-canvas/60 px-2 py-1 text-[11px] text-rose-600 hover:bg-rose-50 transition disabled:opacity-50"
                  :disabled="actionTaskId === task.id"
                  @click.stop="handleCancel(task.id)"
                >
                  {{ actionTaskId === task.id ? "取消中…" : "取消任务" }}
                </button>

                <template v-if="task.status === 'succeeded'">
                  <button
                    type="button"
                    class="rounded-md border border-line/80 bg-canvas/60 px-2 py-1 text-[11px] text-muted hover:text-ink hover:bg-canvas transition disabled:opacity-50"
                    :disabled="actionTaskId === task.id"
                    title="按原配置与提示词重新创建新任务生成"
                    @click.stop="handleRetry(task.id)"
                  >
                    {{ actionTaskId === task.id ? "提交中…" : "再次生成" }}
                  </button>
                  <button
                    type="button"
                    class="rounded-md border border-accent/40 bg-accent/5 px-2 py-1 text-[11px] text-accent font-medium hover:bg-accent/15 transition"
                    title="继承参数并在工作台中修改微调"
                    @click.stop="emit('open-variant', task)"
                  >
                    生成变体…
                  </button>
                </template>

                <template v-if="['failed', 'canceled', 'recovery_needed'].includes(task.status)">
                  <button
                    type="button"
                    class="rounded-md border border-line/80 bg-canvas/60 px-2 py-1 text-[11px] text-accent font-medium hover:bg-accent/10 transition disabled:opacity-50"
                    :disabled="actionTaskId === task.id"
                    @click.stop="handleRetry(task.id)"
                  >
                    {{ actionTaskId === task.id ? "排队中…" : "重新执行" }}
                  </button>
                  <button
                    type="button"
                    class="rounded-md border border-line/80 bg-canvas/60 px-2 py-1 text-[11px] text-muted hover:text-ink hover:bg-canvas transition"
                    title="微调参数或更改模型重试"
                    @click.stop="emit('open-variant', task)"
                  >
                    微调重试…
                  </button>
                </template>
              </div>
            </div>

            <!-- 展开的任务详细面板 -->
            <div
              v-if="selectedTaskDetail?.id === task.id"
              class="mt-1 rounded-xl border border-line/80 bg-canvas/30 p-3 text-xs space-y-2 animate-in fade-in-50 duration-150"
            >
              <div class="flex items-center justify-between text-muted text-[10.5px]">
                <span>ID: {{ selectedTaskDetail.id }}</span>
                <span v-if="selectedTaskDetail.finished_at">
                  耗时: {{ Math.max(1, Math.round((new Date(selectedTaskDetail.finished_at).getTime() - new Date(selectedTaskDetail.created_at).getTime()) / 1000)) }} 秒
                </span>
              </div>

              <div v-if="selectedTaskDetail.references.length > 0">
                <span class="text-[11px] font-medium text-ink">参考图快照 ({{ selectedTaskDetail.references.length }} 张):</span>
                <div class="mt-1 flex gap-1.5 overflow-x-auto py-1">
                  <div
                    v-for="ref in selectedTaskDetail.references"
                    :key="ref.id"
                    class="shrink-0 rounded border border-line bg-white px-2 py-1 text-[10px] text-muted"
                  >
                    <span>#{{ ref.seq }} {{ ref.role || "ref" }}</span>
                  </div>
                </div>
              </div>

              <div v-if="selectedTaskDetail.results.length > 0" class="space-y-1.5 pt-1">
                <span class="text-[11px] font-medium text-emerald-800">生成结果产物 ({{ selectedTaskDetail.results.length }} 项):</span>
                <div class="grid grid-cols-2 gap-2 pt-1">
                  <div
                    v-for="res in selectedTaskDetail.results"
                    :key="res.id"
                    class="flex items-center gap-2 rounded-lg border border-line/80 bg-white p-1.5 shadow-2xs"
                  >
                    <img
                      :src="api.getAiResultContentUrl(res.id)"
                      class="h-12 w-12 rounded object-cover border border-line/40 shrink-0 bg-canvas"
                      alt=""
                    />
                    <div class="min-w-0 flex-1 flex flex-col justify-between">
                      <span class="text-[10px] text-muted truncate">#{{ res.id.slice(-6) }} · {{ res.width }}x{{ res.height }}</span>
                      <div class="mt-1 flex items-center gap-1 flex-wrap">
                        <span
                          v-if="res.imported_asset_id"
                          class="inline-flex items-center gap-0.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[9.5px] font-medium text-emerald-700"
                        >
                          ✓ 已入库 #{{ res.imported_asset_id }}
                        </span>
                        <button
                          v-else
                          type="button"
                          class="rounded bg-accent px-1.5 py-0.5 text-[10px] font-medium text-white hover:bg-blue-700 transition disabled:opacity-50"
                          :disabled="importingResultId === res.id"
                          @click="handleImportResult(res.id)"
                        >
                          {{ importingResultId === res.id ? "…" : "入库" }}
                        </button>
                        <button
                          type="button"
                          class="rounded border border-line/80 bg-canvas/60 px-1.5 py-0.5 text-[10px] text-ink hover:bg-canvas transition"
                          title="以该图为输入进行图生图或二度编辑"
                          @click="emit('continue-edit', res, selectedTaskDetail!)"
                        >
                          继续编辑
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
