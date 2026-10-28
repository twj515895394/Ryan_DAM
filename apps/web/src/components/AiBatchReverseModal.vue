<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api } from "../api/client";
import type {
  AiModelProfile,
  AiReverseTemplate,
  AiTaskDetail,
  AiTaskItem,
  AssetOut
} from "../api/types";
import SidebarIcon from "./SidebarIcon.vue";
import ConfirmDialog from "./ConfirmDialog.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";
import { notify } from "../stores/library";

const props = defineProps<{
  open: boolean;
  selectedAssets: AssetOut[];
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "task-started", taskId: string): void;
  (e: "committed"): void;
}>();

// 步骤：'config'（配置模板发起） | 'review'（审查与采纳待审结果）
const step = ref<"config" | "review">("config");

const loading = ref(false);
const submitting = ref(false);
const committing = ref(false);
const error = ref("");

// 配置项
const templates = ref<AiReverseTemplate[]>([]);
const visionModels = ref<AiModelProfile[]>([]);
const selectedTemplateId = ref<number | null>(null);
const selectedModelProfileId = ref<number | null>(null);
const customInstruction = ref("");

const visionModelOptions = computed<AppleSelectOption[]>(() =>
  visionModels.value.map((m) => ({
    value: m.id,
    label: m.name,
    subLabel: m.model_id,
    badge: m.adapter_kind,
    badgeColor: "blue" as const
  }))
);

// 批量任务轮询与审查数据
const currentTaskId = ref<string | null>(null);
const taskDetail = ref<AiTaskDetail | null>(null);
let pollTimer: any = null;

// 待审项目选中项与编辑草稿
const selectedItemIds = ref<number[]>([]);
const editedDrafts = ref<Record<number, string>>({});
const filterNoPromptOnly = ref(false);
const showOverwriteConfirm = ref(false);

const filteredItems = computed(() => {
  if (!taskDetail.value?.items) return [];
  if (!filterNoPromptOnly.value) return taskDetail.value.items;
  return taskDetail.value.items.filter((item) => !item.current_prompt_text || !item.current_prompt_text.trim());
});

const isAllSelected = computed(() => {
  if (filteredItems.value.length === 0) return false;
  return filteredItems.value.every((it) => selectedItemIds.value.includes(it.id));
});

const succeededSelectedCount = computed(() => {
  const set = new Set(selectedItemIds.value);
  return taskDetail.value?.items.filter((it) => set.has(it.id) && it.status === "succeeded").length || 0;
});

const hasConflictSelected = computed(() => {
  const set = new Set(selectedItemIds.value);
  return (
    taskDetail.value?.items.some(
      (it) => set.has(it.id) && it.status === "succeeded" && it.current_prompt_text && it.current_prompt_text.trim()
    ) || false
  );
});

watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      step.value = "config";
      error.value = "";
      currentTaskId.value = null;
      taskDetail.value = null;
      selectedItemIds.value = [];
      editedDrafts.value = {};
      filterNoPromptOnly.value = false;
      showOverwriteConfirm.value = false;
      stopPolling();
      await loadInitialData();
    } else {
      stopPolling();
    }
  },
  { immediate: true }
);

function stopPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function loadInitialData(): Promise<void> {
  loading.value = true;
  try {
    const [tpls, models] = await Promise.all([api.listReverseTemplates(true), api.listAllModels()]);
    templates.value = tpls;
    if (tpls.length > 0 && !selectedTemplateId.value) {
      selectedTemplateId.value = tpls[0].id;
    }
    visionModels.value = models.filter((m) => m.enabled && m.capabilities?.image_understand?.supported);
    if (visionModels.value.length > 0 && !selectedModelProfileId.value) {
      selectedModelProfileId.value = visionModels.value[0].id;
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载配置失败";
  } finally {
    loading.value = false;
  }
}

async function handleStartBatchReverse(): Promise<void> {
  if (props.selectedAssets.length === 0) return;
  submitting.value = true;
  error.value = "";
  try {
    const task = await api.submitBatchReverse({
      asset_ids: props.selectedAssets.map((a) => a.id),
      template_id: selectedTemplateId.value,
      model_profile_id: selectedModelProfileId.value,
      user_instruction: customInstruction.value.trim() || undefined,
    });
    currentTaskId.value = task.id;
    step.value = "review";
    emit("task-started", task.id);
    await fetchTaskStatus();
    startPolling();
  } catch (err: any) {
    error.value = err?.message || (err instanceof Error ? err.message : "发起批量反推失败");
  } finally {
    submitting.value = false;
  }
}

function startPolling(): void {
  stopPolling();
  pollTimer = setInterval(async () => {
    await fetchTaskStatus();
  }, 2000);
}

async function fetchTaskStatus(): Promise<void> {
  if (!currentTaskId.value) return;
  try {
    const task = await api.getAiTask(currentTaskId.value);
    taskDetail.value = task;

    // 默认全选成功的条目（如果之前为空）
    if (selectedItemIds.value.length === 0 && task.items.length > 0) {
      selectedItemIds.value = task.items.filter((it) => it.status === "succeeded").map((it) => it.id);
    }

    if (task.status === "succeeded" || task.status === "failed" || task.status === "canceled") {
      stopPolling();
    }
  } catch (err) {
    // 忽略瞬态轮询错误
  }
}

function toggleSelectAll(): void {
  if (isAllSelected.value) {
    selectedItemIds.value = [];
  } else {
    selectedItemIds.value = filteredItems.value.map((it) => it.id);
  }
}

function toggleItemSelection(id: number): void {
  const idx = selectedItemIds.value.indexOf(id);
  if (idx >= 0) {
    selectedItemIds.value.splice(idx, 1);
  } else {
    selectedItemIds.value.push(id);
  }
}

async function handleDraftBlur(item: AiTaskItem): Promise<void> {
  const currentDraft = editedDrafts.value[item.id];
  if (currentDraft !== undefined && currentDraft.trim() !== (item.draft_prompt_text || "")) {
    try {
      if (!currentTaskId.value) return;
      await api.updateTaskItemDraft(currentTaskId.value, item.id, {
        draft_prompt_text: currentDraft,
      });
      item.draft_prompt_text = currentDraft;
    } catch {
      // 容错保留本地草稿
    }
  }
}

function handleCommitClick(): void {
  if (hasConflictSelected.value) {
    showOverwriteConfirm.value = true;
  } else {
    void executeCommit(false);
  }
}

async function executeCommit(allowOverwrite: boolean): Promise<void> {
  showOverwriteConfirm.value = false;
  if (!currentTaskId.value || selectedItemIds.value.length === 0) return;

  committing.value = true;
  error.value = "";
  try {
    const res = await api.commitBatchReverseItems(currentTaskId.value, {
      item_ids: selectedItemIds.value,
      edited_drafts: editedDrafts.value,
      allow_overwrite: allowOverwrite,
    });

    if (res.conflict_count > 0 && !allowOverwrite) {
      notify("error", `已采纳 ${res.committed_count} 项，${res.conflict_count} 项存在已有提示词未覆盖`);
    } else {
      notify("success", `成功采纳并录入 ${res.committed_count} 项资产提示词`);
    }

    await fetchTaskStatus();
    emit("committed");
    if (res.committed_count > 0 && res.conflict_count === 0) {
      emit("close");
    }
  } catch (err: any) {
    error.value = err?.message || (err instanceof Error ? err.message : "采纳提示词失败");
  } finally {
    committing.value = false;
  }
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 animate-fade-in"
    @click.self="emit('close')"
  >
    <div
      class="flex max-h-[85vh] w-full max-w-4xl flex-col rounded-2xl border border-line bg-white/95 shadow-2xl backdrop-blur-xl"
    >
      <!-- 头部 -->
      <div class="flex items-center justify-between border-b border-line px-6 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent">
            <SidebarIcon name="star" class="h-5 w-5" />
          </div>
          <div>
            <h3 class="text-base font-semibold text-ink">
              {{ step === "config" ? "批量反推视觉提示词" : "批量反推审查与采纳" }}
            </h3>
            <p class="text-xs text-muted">
              {{
                step === "config"
                  ? `已选择 ${selectedAssets.length} 张图片资产`
                  : `任务 #${currentTaskId} · 进度 ${taskDetail?.progress_pct || 0}%`
              }}
            </p>
          </div>
        </div>

        <button
          type="button"
          class="rounded-lg p-1.5 text-muted transition hover:bg-canvas hover:text-ink"
          @click="emit('close')"
        >
          <SidebarIcon name="close" class="h-5 w-5" />
        </button>
      </div>

      <!-- 错误提示 -->
      <div v-if="error" class="border-b border-rose-100 bg-rose-50 px-6 py-2.5 text-xs text-rose-600">
        {{ error }}
      </div>

      <!-- 第一步：配置与启动 -->
      <div v-if="step === 'config'" class="space-y-5 overflow-y-auto px-6 py-5">
        <div>
          <label class="block text-xs font-semibold uppercase tracking-wider text-muted">反推风格模板</label>
          <div class="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <button
              v-for="tpl in templates"
              :key="tpl.id"
              type="button"
              class="flex flex-col items-start rounded-xl border p-3 text-left transition"
              :class="
                selectedTemplateId === tpl.id
                  ? 'border-accent bg-accent/5 ring-1 ring-accent'
                  : 'border-line hover:border-accent/40 hover:bg-canvas'
              "
              @click="selectedTemplateId = tpl.id"
            >
              <span class="text-sm font-medium text-ink">{{ tpl.name }}</span>
              <span class="mt-1 line-clamp-2 text-xs text-muted">{{ tpl.description || "提取主体特征与质感" }}</span>
            </button>
          </div>
        </div>

        <div>
          <label class="block text-xs font-semibold uppercase tracking-wider text-muted mb-2">视觉理解模型</label>
          <AppleSelect
            v-model="selectedModelProfileId"
            :options="visionModelOptions"
            placeholder="请选择视觉理解模型"
          />
        </div>

        <div>
          <label class="block text-xs font-semibold uppercase tracking-wider text-muted">
            补充自定义反推要求（可选）
          </label>
          <textarea
            v-model="customInstruction"
            rows="2"
            placeholder="例如：着重分析画面光影角度、色彩情绪与材质，或要求英文输出…"
            class="mt-2 w-full resize-none rounded-xl border border-line bg-canvas/40 px-3 py-2 text-xs text-ink outline-none transition placeholder:text-muted/60 focus:border-accent focus:bg-white focus:ring-1 focus:ring-accent"
          />
        </div>

        <!-- 选中素材预览清单摘要 -->
        <div>
          <label class="block text-xs font-semibold uppercase tracking-wider text-muted">
            待处理资产清单 ({{ selectedAssets.length }})
          </label>
          <div class="mt-2 flex max-h-36 flex-wrap gap-2 overflow-y-auto rounded-xl border border-line p-3">
            <div
              v-for="a in selectedAssets"
              :key="a.id"
              class="flex items-center gap-1.5 rounded-lg border border-line bg-canvas px-2.5 py-1 text-xs text-ink"
            >
              <SidebarIcon name="image" class="h-3.5 w-3.5 text-muted" />
              <span class="max-w-[140px] truncate" :title="a.name">{{ a.name }}</span>
              <span v-if="a.has_prompt" class="rounded bg-amber-100 px-1 text-[10px] text-amber-800" title="已有提示词">
                有词
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 第二步：审查与采纳待审列表 -->
      <div v-else class="flex flex-1 flex-col overflow-hidden">
        <!-- 进度与过滤工具栏 -->
        <div class="flex items-center justify-between border-b border-line bg-canvas/40 px-6 py-3">
          <div class="flex items-center gap-2">
            <label class="flex items-center gap-1.5 text-xs font-medium text-ink cursor-pointer select-none">
              <span class="flex h-9 w-9 items-center justify-center">
                <input
                  type="checkbox"
                  :checked="isAllSelected"
                  class="h-4 w-4 rounded border-line text-accent focus:ring-accent"
                  @change="toggleSelectAll"
                />
              </span>
              <span>全选当前显示</span>
            </label>
            <label class="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none">
              <span class="flex h-9 w-9 items-center justify-center">
                <input
                  v-model="filterNoPromptOnly"
                  type="checkbox"
                  class="h-4 w-4 rounded border-line text-accent focus:ring-accent"
                />
              </span>
              <span>仅看尚未设置提示词的素材</span>
            </label>
          </div>

          <div class="flex items-center gap-2 text-xs text-muted">
            <span v-if="taskDetail?.status === 'running'" class="flex items-center gap-1.5 text-accent font-medium">
              <span class="inline-block h-2 w-2 animate-ping rounded-full bg-accent" />
              反推处理中 ({{ taskDetail.progress_pct }}%)…
            </span>
            <span v-else-if="taskDetail?.status === 'succeeded'" class="text-emerald-600 font-medium">
              ✓ 反推全部完成
            </span>
          </div>
        </div>

        <!-- 逐项列表 -->
        <div class="flex-1 overflow-y-auto divide-y divide-line p-4">
          <div
            v-for="item in filteredItems"
            :key="item.id"
            class="flex items-start gap-4 p-3 transition rounded-xl"
            :class="selectedItemIds.includes(item.id) ? 'bg-accent/5' : 'hover:bg-canvas/60'"
          >
            <div class="flex h-9 w-9 shrink-0 items-center justify-center">
              <input
                type="checkbox"
                :checked="selectedItemIds.includes(item.id)"
                :disabled="item.status !== 'succeeded'"
                class="h-4 w-4 rounded border-line text-accent focus:ring-accent"
                @change="toggleItemSelection(item.id)"
              />
            </div>

            <!-- 资产名称与状态 -->
            <div class="w-40 shrink-0">
              <div class="text-xs font-medium text-ink truncate" :title="item.asset_name || `资产 #${item.asset_id}`">
                {{ item.asset_name || `资产 #${item.asset_id}` }}
              </div>
              <div class="mt-1 flex items-center gap-1.5">
                <span
                  class="rounded px-1.5 py-0.5 text-[10px] font-medium"
                  :class="{
                    'bg-amber-100 text-amber-800': item.status === 'pending' || item.status === 'running',
                    'bg-emerald-100 text-emerald-800': item.status === 'succeeded',
                    'bg-rose-100 text-rose-800': item.status === 'failed',
                    'bg-blue-100 text-blue-800': item.status === 'committed',
                  }"
                >
                  {{
                    item.status === "succeeded"
                      ? "反推完成"
                      : item.status === "running"
                      ? "处理中"
                      : item.status === "committed"
                      ? "已采纳"
                      : item.status === "failed"
                      ? "失败"
                      : "排队中"
                  }}
                </span>
                <span
                  v-if="item.current_prompt_text"
                  class="rounded bg-amber-50 px-1 py-0.5 text-[10px] text-amber-700 border border-amber-200"
                  title="该资产已有提示词，采纳将触发覆盖"
                >
                  已有词
                </span>
              </div>
            </div>

            <!-- 对比与编辑区域 -->
            <div class="flex-1 space-y-2">
              <div v-if="item.current_prompt_text" class="rounded-lg bg-canvas p-2 text-xs text-muted">
                <div class="text-[10px] font-semibold uppercase text-muted/70">资产当前提示词：</div>
                <div class="mt-0.5 line-clamp-2">{{ item.current_prompt_text }}</div>
              </div>

              <div>
                <textarea
                  :value="editedDrafts[item.id] !== undefined ? editedDrafts[item.id] : (item.draft_prompt_text || '')"
                  :disabled="item.status !== 'succeeded'"
                  rows="2"
                  placeholder="反推处理完成后将显示提示词草稿，可直接内联微调…"
                  class="w-full resize-none rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none transition focus:border-accent focus:ring-1 focus:ring-accent disabled:bg-canvas disabled:text-muted"
                  @input="editedDrafts[item.id] = ($event.target as HTMLTextAreaElement).value"
                  @blur="handleDraftBlur(item)"
                />
              </div>

              <div v-if="item.error_message" class="text-xs text-rose-600">
                失败原因：{{ item.error_message }}
              </div>
            </div>
          </div>

          <div v-if="filteredItems.length === 0" class="py-12 text-center text-xs text-muted">
            没有符合当前筛选条件的任务项
          </div>
        </div>
      </div>

      <!-- 底部操作栏 -->
      <div class="flex items-center justify-between border-t border-line bg-canvas/30 px-6 py-4">
        <button
          v-if="step === 'review'"
          type="button"
          class="text-xs text-muted hover:text-ink transition"
          @click="step = 'config'"
        >
          ← 返回重新配置
        </button>
        <div v-else />

        <div class="flex items-center gap-3">
          <button
            type="button"
            class="rounded-xl px-4 py-2 text-xs font-medium text-muted transition hover:bg-canvas hover:text-ink"
            @click="emit('close')"
          >
            关闭
          </button>

          <button
            v-if="step === 'config'"
            type="button"
            class="flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-medium text-white shadow-soft transition hover:bg-accent/90 disabled:opacity-50"
            :disabled="submitting || loading || selectedAssets.length === 0"
            @click="handleStartBatchReverse"
          >
            <SidebarIcon name="refresh" class="h-3.5 w-3.5" :class="submitting ? 'animate-spin' : ''" />
            <span>{{ submitting ? "提交任务中…" : `开始反推 (${selectedAssets.length})` }}</span>
          </button>

          <button
            v-else
            type="button"
            class="flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-medium text-white shadow-soft transition hover:bg-accent/90 disabled:opacity-50"
            :disabled="committing || succeededSelectedCount === 0"
            @click="handleCommitClick"
          >
            <SidebarIcon v-if="committing" name="refresh" class="h-3.5 w-3.5 animate-spin" />
            <SidebarIcon v-else name="check" class="h-3.5 w-3.5" />
            <span>{{ committing ? "采纳录入中…" : `批量采纳并录入 (${succeededSelectedCount})` }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 覆盖警示确认弹窗 -->
    <ConfirmDialog
      :open="showOverwriteConfirm"
      title="确认覆盖已有提示词？"
      :message="`选中的待录入项中，有素材已存在提示词。采纳后将覆盖原有提示词并将来源标记为 'ai_reverse'，是否继续覆盖？`"
      intent="warning"
      confirm-text="确认覆盖录入"
      cancel-text="取消"
      @confirm="executeCommit(true)"
      @cancel="showOverwriteConfirm = false"
    />
  </div>
</template>
