<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import type {
  AiCreationPreset,
  AiReverseTemplate,
  AiReverseTemplateCreatePayload
} from "../api/types";
import type { ConfirmRequest } from "../composables/useConfirmDialog";
import SidebarIcon from "./SidebarIcon.vue";
import AppleSelect, { type AppleSelectOption } from "./AppleSelect.vue";
import { notify } from "../stores/library";

const props = defineProps<{
  onAskConfirm?: (request: ConfirmRequest) => void;
}>();

// ── 子 Tab：反推模板 vs 创作预设 ─────────────────────────────────────────
const subTab = ref<"reverse" | "presets">("reverse");

// ── 反推模板状态 ────────────────────────────────────────────────────────
const reverseTemplates = ref<AiReverseTemplate[]>([]);
const loadingReverse = ref(false);
const expandedReverseIds = ref<Set<number>>(new Set());

// 新增 / 编辑反推模板表单
const showAddReverse = ref(false);
const editingReverseId = ref<number | null>(null);
const savingReverse = ref(false);
const reverseFormError = ref("");
const reverseForm = ref<AiReverseTemplateCreatePayload>({
  name: "",
  code: "",
  description: "",
  system_prompt: "",
  enabled: true
});

// ── 创作预设状态 ────────────────────────────────────────────────────────
const creationPresets = ref<AiCreationPreset[]>([]);
const loadingPresets = ref(false);
const expandedPresetIds = ref<Set<number>>(new Set());

// 新增 / 编辑创作预设表单
const showAddPreset = ref(false);
const editingPresetId = ref<number | null>(null);
const savingPreset = ref(false);
const presetFormError = ref("");
const presetForm = ref<{
  name: string;
  code: string;
  description: string;
  creation_mode: "image_generate" | "image_edit";
  system_rules: string;
  negative_prompt: string;
}>({
  name: "",
  code: "",
  description: "",
  creation_mode: "image_generate",
  system_rules: "",
  negative_prompt: ""
});

const creationModeOptions: AppleSelectOption[] = [
  { value: "image_generate", label: "文生图创作 (image_generate)", badge: "生图", badgeColor: "emerald" },
  { value: "image_edit", label: "图生图与编辑 (image_edit)", badge: "编辑", badgeColor: "blue" }
];

// ── 数据加载 ────────────────────────────────────────────────────────────
async function loadReverseTemplates(): Promise<void> {
  loadingReverse.value = true;
  try {
    reverseTemplates.value = await api.listReverseTemplates(false);
  } catch (err: any) {
    notify("error", `加载反推模板失败: ${err.message || err}`);
  } finally {
    loadingReverse.value = false;
  }
}

async function loadCreationPresets(): Promise<void> {
  loadingPresets.value = true;
  try {
    creationPresets.value = await api.listCreationPresets(undefined as any, false);
  } catch (err: any) {
    notify("error", `加载创作预设失败: ${err.message || err}`);
  } finally {
    loadingPresets.value = false;
  }
}

// ── 反推模板操作 ────────────────────────────────────────────────────────
function toggleExpandReverse(id: number): void {
  if (expandedReverseIds.value.has(id)) {
    expandedReverseIds.value.delete(id);
  } else {
    expandedReverseIds.value.add(id);
  }
}

function openAddReverseModal(): void {
  editingReverseId.value = null;
  reverseForm.value = {
    name: "",
    code: "",
    description: "",
    system_prompt: "",
    enabled: true
  };
  reverseFormError.value = "";
  showAddReverse.value = true;
}

function openEditReverseModal(tpl: AiReverseTemplate): void {
  editingReverseId.value = tpl.id;
  reverseForm.value = {
    name: tpl.name,
    code: tpl.code || "",
    description: tpl.description || "",
    system_prompt: tpl.system_prompt,
    enabled: tpl.enabled
  };
  reverseFormError.value = "";
  showAddReverse.value = true;
}

async function handleSaveReverse(): Promise<void> {
  if (!reverseForm.value.name.trim()) {
    reverseFormError.value = "请输入模板名称";
    return;
  }
  if (!reverseForm.value.system_prompt.trim()) {
    reverseFormError.value = "请输入反推系统提示词 (System Prompt)";
    return;
  }
  savingReverse.value = true;
  reverseFormError.value = "";
  try {
    const payload: AiReverseTemplateCreatePayload = {
      name: reverseForm.value.name.trim(),
      code: reverseForm.value.code?.trim() || null,
      description: reverseForm.value.description?.trim() || null,
      system_prompt: reverseForm.value.system_prompt.trim(),
      enabled: true
    };
    if (editingReverseId.value) {
      await api.updateReverseTemplate(editingReverseId.value, payload);
      notify("success", "视觉反推模板已更新");
    } else {
      await api.createReverseTemplate(payload);
      notify("success", "自定义视觉反推模板已创建");
    }
    showAddReverse.value = false;
    editingReverseId.value = null;
    await loadReverseTemplates();
  } catch (err: any) {
    reverseFormError.value = err.message || (editingReverseId.value ? "更新反推模板失败" : "创建反推模板失败");
  } finally {
    savingReverse.value = false;
  }
}

function handleResetReverse(tpl: AiReverseTemplate): void {
  const doReset = async () => {
    try {
      await api.resetReverseTemplate(tpl.id);
      notify("success", `反推模板「${tpl.name}」已恢复为系统初始配置`);
      await loadReverseTemplates();
    } catch (err: any) {
      notify("error", `重置失败: ${err.message || err}`);
    }
  };

  if (props.onAskConfirm) {
    props.onAskConfirm({
      title: "恢复系统默认反推模板",
      description: `确定要将「${tpl.name}」恢复为系统初始预设吗？您对其进行的自定义修改将被重置。`,
      intent: "warning",
      confirmText: "恢复默认",
      action: () => void doReset()
    });
  } else {
    void doReset();
  }
}

function handleDeleteReverse(tpl: AiReverseTemplate): void {
  if (tpl.is_builtin) {
    notify("error", "系统内置反推模板无法删除");
    return;
  }
  const doDelete = async () => {
    try {
      await api.deleteReverseTemplate(tpl.id);
      notify("success", `反推模板「${tpl.name}」已删除`);
      await loadReverseTemplates();
    } catch (err: any) {
      notify("error", `删除失败: ${err.message || err}`);
    }
  };

  if (props.onAskConfirm) {
    props.onAskConfirm({
      title: "删除自定义反推模板",
      description: `确定要删除反推模板「${tpl.name}」吗？此操作无法撤销。`,
      intent: "danger",
      confirmText: "彻底删除",
      action: () => void doDelete()
    });
  } else {
    void doDelete();
  }
}

// ── 创作预设操作 ────────────────────────────────────────────────────────
function toggleExpandPreset(id: number): void {
  if (expandedPresetIds.value.has(id)) {
    expandedPresetIds.value.delete(id);
  } else {
    expandedPresetIds.value.add(id);
  }
}

function openAddPresetModal(): void {
  editingPresetId.value = null;
  presetForm.value = {
    name: "",
    code: "",
    description: "",
    creation_mode: "image_generate",
    system_rules: "",
    negative_prompt: ""
  };
  presetFormError.value = "";
  showAddPreset.value = true;
}

function openEditPresetModal(preset: AiCreationPreset): void {
  editingPresetId.value = preset.id;
  presetForm.value = {
    name: preset.name,
    code: preset.code || "",
    description: preset.description || "",
    creation_mode: preset.creation_mode === "image_edit" ? "image_edit" : "image_generate",
    system_rules: preset.system_rules || "",
    negative_prompt: preset.default_params?.negative_prompt || ""
  };
  presetFormError.value = "";
  showAddPreset.value = true;
}

async function handleSavePreset(): Promise<void> {
  if (!presetForm.value.name.trim()) {
    presetFormError.value = "请输入预设名称";
    return;
  }
  savingPreset.value = true;
  presetFormError.value = "";
  try {
    const payload: Partial<AiCreationPreset> = {
      name: presetForm.value.name.trim(),
      code: presetForm.value.code?.trim() || null,
      description: presetForm.value.description?.trim() || null,
      creation_mode: presetForm.value.creation_mode,
      system_rules: presetForm.value.system_rules.trim() || null,
      default_params: {
        negative_prompt: presetForm.value.negative_prompt.trim() || undefined
      },
      enabled: true
    };
    if (editingPresetId.value) {
      await api.updateCreationPreset(editingPresetId.value, payload);
      notify("success", "创作风格预设已更新");
    } else {
      await api.createCreationPreset(payload);
      notify("success", "自定义创作风格预设已创建");
    }
    showAddPreset.value = false;
    editingPresetId.value = null;
    await loadCreationPresets();
  } catch (err: any) {
    presetFormError.value = err.message || (editingPresetId.value ? "更新创作预设失败" : "创建创作预设失败");
  } finally {
    savingPreset.value = false;
  }
}

function handleResetPreset(preset: AiCreationPreset): void {
  const doReset = async () => {
    try {
      await api.resetCreationPreset(preset.id);
      notify("success", `创作预设「${preset.name}」已恢复为系统初始配置`);
      await loadCreationPresets();
    } catch (err: any) {
      notify("error", `重置失败: ${err.message || err}`);
    }
  };

  if (props.onAskConfirm) {
    props.onAskConfirm({
      title: "恢复系统默认创作预设",
      description: `确定要将创作预设「${preset.name}」恢复为系统初始配置吗？自定义修改将被重置。`,
      intent: "warning",
      confirmText: "恢复默认",
      action: () => void doReset()
    });
  } else {
    void doReset();
  }
}

function handleDeletePreset(preset: AiCreationPreset): void {
  if (preset.is_builtin) {
    notify("error", "系统内置创作风格预设无法删除");
    return;
  }
  const doDelete = async () => {
    try {
      await api.deleteCreationPreset(preset.id);
      notify("success", `创作预设「${preset.name}」已删除`);
      await loadCreationPresets();
    } catch (err: any) {
      notify("error", `删除失败: ${err.message || err}`);
    }
  };

  if (props.onAskConfirm) {
    props.onAskConfirm({
      title: "删除自定义创作预设",
      description: `确定要删除创作风格预设「${preset.name}」吗？此操作无法撤销。`,
      intent: "danger",
      confirmText: "彻底删除",
      action: () => void doDelete()
    });
  } else {
    void doDelete();
  }
}

onMounted(() => {
  void loadReverseTemplates();
  void loadCreationPresets();
});
</script>

<template>
  <div class="space-y-4">
    <!-- 顶部说明与子 Segment 切换 -->
    <div class="flex items-center justify-between border-b border-line/60 pb-3">
      <div>
        <h4 class="text-xs font-semibold text-ink">提示词模板与创作风格预设</h4>
        <p class="text-[11px] text-muted">
          管理视觉反推 Prompt 模板规则与工作台风格预设。支持查看系统内置指令及创建个人定制配置。
        </p>
      </div>

      <!-- Apple HIG 2-Segment Tab -->
      <div class="flex rounded-lg bg-canvas p-0.5 border border-line/60 text-xs font-medium">
        <button
          type="button"
          class="rounded-md px-3 py-1 transition-all"
          :class="subTab === 'reverse' ? 'bg-white text-ink shadow-2xs font-semibold' : 'text-muted hover:text-ink'"
          @click="subTab = 'reverse'"
        >
          👁️ 视觉反推模板
        </button>
        <button
          type="button"
          class="rounded-md px-3 py-1 transition-all"
          :class="subTab === 'presets' ? 'bg-white text-ink shadow-2xs font-semibold' : 'text-muted hover:text-ink'"
          @click="subTab = 'presets'"
        >
          🎨 创作风格预设
        </button>
      </div>
    </div>

    <!-- ───────────────────────── TAB 1: 视觉反推模板 ───────────────────────── -->
    <div v-if="subTab === 'reverse'" class="space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-xs font-semibold text-ink">
          已配置反推模板 ({{ reverseTemplates.length }})
        </span>
        <button
          type="button"
          class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white shadow-xs transition hover:bg-accent/90"
          @click="openAddReverseModal"
        >
          <SidebarIcon name="plus" class="h-3 w-3" />
          <span>添加反推模板</span>
        </button>
      </div>

      <div v-if="loadingReverse" class="py-6 text-center text-xs text-muted">
        正在读取反推模板…
      </div>

      <div v-else-if="reverseTemplates.length === 0" class="rounded-xl border border-dashed border-line bg-canvas/40 p-5 text-center text-xs text-muted">
        暂无反推模板配置
      </div>

      <div v-else class="space-y-2.5">
        <div
          v-for="tpl in reverseTemplates"
          :key="tpl.id"
          class="rounded-xl border border-line/80 bg-white p-3 shadow-2xs transition hover:border-line"
        >
          <div class="flex items-start justify-between">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-xs text-ink">{{ tpl.name }}</span>
                <span v-if="tpl.code" class="rounded bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-muted border border-line/50">
                  {{ tpl.code }}
                </span>
                <span
                  class="rounded-md px-1.5 py-0.2 text-[10px] font-medium"
                  :class="tpl.is_builtin ? 'bg-zinc-100 text-zinc-600 border border-zinc-200/60' : 'bg-accent/10 text-accent border border-accent/20'"
                >
                  {{ tpl.is_builtin ? "系统内置" : "自定义模板" }}
                </span>
              </div>
              <p class="mt-1 text-xs text-muted/90">
                {{ tpl.description || "无描述说明" }}
              </p>
            </div>

            <div class="flex items-center gap-1.5 shrink-0 ml-3">
              <button
                type="button"
                class="rounded-md border border-line/70 bg-canvas/40 px-2 py-1 text-[11px] font-medium text-ink hover:bg-canvas transition"
                @click="toggleExpandReverse(tpl.id)"
              >
                {{ expandedReverseIds.has(tpl.id) ? "收起提示词" : "查看提示词" }}
              </button>
              <button
                type="button"
                class="rounded-md border border-line/70 bg-canvas/40 px-2 py-1 text-[11px] font-medium text-ink hover:bg-canvas transition"
                title="编辑模板规则"
                @click="openEditReverseModal(tpl)"
              >
                编辑
              </button>
              <button
                v-if="tpl.is_builtin"
                type="button"
                class="rounded-md border border-line/70 bg-canvas/40 px-2 py-1 text-[11px] font-medium text-amber-700 hover:bg-amber-50 hover:border-amber-200 transition"
                title="重置为系统默认配置"
                @click="handleResetReverse(tpl)"
              >
                恢复默认
              </button>
              <button
                v-if="!tpl.is_builtin"
                type="button"
                class="rounded-md p-1 text-muted hover:bg-rose-50 hover:text-rose-600 transition"
                title="删除自定义模板"
                @click="handleDeleteReverse(tpl)"
              >
                <SidebarIcon name="close" class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          <!-- 提示词展开区 -->
          <div
            v-if="expandedReverseIds.has(tpl.id)"
            class="mt-2.5 rounded-lg border border-line/60 bg-canvas/50 p-2.5 text-xs font-mono text-ink/80 leading-relaxed max-h-48 overflow-y-auto"
          >
            <div class="flex items-center justify-between pb-1 mb-1 border-b border-line/40 text-[10px] text-muted uppercase">
              <span>视觉模型系统提示词 (System Prompt)</span>
              <span>{{ tpl.system_prompt.length }} 字符</span>
            </div>
            <pre class="whitespace-pre-wrap font-sans text-xs text-ink/90">{{ tpl.system_prompt }}</pre>
          </div>
        </div>
      </div>

      <!-- 添加/编辑反推模板抽屉 -->
      <div
        v-if="showAddReverse"
        class="mt-3 rounded-xl border border-line bg-canvas/50 p-4 space-y-3"
      >
        <div class="flex items-center justify-between border-b border-line/60 pb-2">
          <h5 class="text-xs font-semibold text-ink">
            {{ editingReverseId ? "编辑视觉反推模板" : "添加自定义视觉反推模板" }}
          </h5>
          <button class="text-xs text-muted hover:text-ink" @click="showAddReverse = false">取消</button>
        </div>

        <div class="space-y-2.5 text-xs">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-medium text-ink/80 mb-1">模板名称 *</label>
              <input
                v-model="reverseForm.name"
                type="text"
                placeholder="例如：电商白底产品反推 / 二次元角色特征"
                class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
              />
            </div>
            <div>
              <label class="block text-[11px] font-medium text-ink/80 mb-1">英文标识 Code（选填）</label>
              <input
                v-model="reverseForm.code"
                type="text"
                placeholder="例如：ecommerce_product"
                class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
              />
            </div>
          </div>

          <div>
            <label class="block text-[11px] font-medium text-ink/80 mb-1">模板说明描述</label>
            <input
              v-model="reverseForm.description"
              type="text"
              placeholder="简要概括该模板重点提取的视觉信息与适用场景"
              class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
            />
          </div>

          <div>
            <label class="block text-[11px] font-medium text-ink/80 mb-1">系统提示词 (System Prompt) *</label>
            <textarea
              v-model="reverseForm.system_prompt"
              rows="4"
              placeholder="输入传给视觉大模型的 System Prompt 指令，指导模型如何从图片中提取构图、光影、色彩或主体细节…"
              class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent leading-relaxed"
            />
          </div>

          <p v-if="reverseFormError" class="text-[11px] text-rose-600">{{ reverseFormError }}</p>

          <div class="flex justify-end gap-2 pt-2 border-t border-line/60">
            <button
              type="button"
              class="rounded-md border border-line bg-white px-3 py-1 text-xs text-ink hover:bg-canvas transition"
              @click="showAddReverse = false"
            >
              取消
            </button>
            <button
              type="button"
              class="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 transition disabled:opacity-50"
              :disabled="savingReverse"
              @click="handleSaveReverse"
            >
              {{ savingReverse ? "正在保存…" : editingReverseId ? "保存修改" : "保存模板" }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ───────────────────────── TAB 2: 创作风格预设 ───────────────────────── -->
    <div v-else class="space-y-3">
      <div class="flex items-center justify-between">
        <span class="text-xs font-semibold text-ink">
          已配置创作风格预设 ({{ creationPresets.length }})
        </span>
        <button
          type="button"
          class="flex items-center gap-1 rounded-lg bg-accent px-2.5 py-1 text-xs font-medium text-white shadow-xs transition hover:bg-accent/90"
          @click="openAddPresetModal"
        >
          <SidebarIcon name="plus" class="h-3 w-3" />
          <span>添加创作预设</span>
        </button>
      </div>

      <div v-if="loadingPresets" class="py-6 text-center text-xs text-muted">
        正在读取创作预设…
      </div>

      <div v-else-if="creationPresets.length === 0" class="rounded-xl border border-dashed border-line bg-canvas/40 p-5 text-center text-xs text-muted">
        暂无创作预设配置
      </div>

      <div v-else class="space-y-2.5">
        <div
          v-for="p in creationPresets"
          :key="p.id"
          class="rounded-xl border border-line/80 bg-white p-3 shadow-2xs transition hover:border-line"
        >
          <div class="flex items-start justify-between">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-xs text-ink">{{ p.name }}</span>
                <span v-if="p.code" class="rounded bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-muted border border-line/50">
                  {{ p.code }}
                </span>
                <span
                  class="rounded-md px-1.5 py-0.2 text-[10px] font-medium"
                  :class="p.is_builtin ? 'bg-zinc-100 text-zinc-600 border border-zinc-200/60' : 'bg-accent/10 text-accent border border-accent/20'"
                >
                  {{ p.is_builtin ? "系统内置" : "自定义预设" }}
                </span>
                <span class="rounded bg-canvas px-1.5 py-0.2 text-[10px] text-muted font-mono">
                  {{ p.creation_mode }}
                </span>
              </div>
              <p class="mt-1 text-xs text-muted/90">
                {{ p.description || "无描述说明" }}
              </p>
            </div>

            <div class="flex items-center gap-1.5 shrink-0 ml-3">
              <button
                type="button"
                class="rounded-md border border-line/70 bg-canvas/40 px-2 py-1 text-[11px] font-medium text-ink hover:bg-canvas transition"
                @click="toggleExpandPreset(p.id)"
              >
                {{ expandedPresetIds.has(p.id) ? "收起规则" : "查看规则" }}
              </button>
              <button
                type="button"
                class="rounded-md border border-line/70 bg-canvas/40 px-2 py-1 text-[11px] font-medium text-ink hover:bg-canvas transition"
                title="编辑预设规则"
                @click="openEditPresetModal(p)"
              >
                编辑
              </button>
              <button
                v-if="p.is_builtin"
                type="button"
                class="rounded-md border border-line/70 bg-canvas/40 px-2 py-1 text-[11px] font-medium text-amber-700 hover:bg-amber-50 hover:border-amber-200 transition"
                title="重置为系统默认配置"
                @click="handleResetPreset(p)"
              >
                恢复默认
              </button>
              <button
                v-if="!p.is_builtin"
                type="button"
                class="rounded-md p-1 text-muted hover:bg-rose-50 hover:text-rose-600 transition"
                title="删除自定义预设"
                @click="handleDeletePreset(p)"
              >
                <SidebarIcon name="close" class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          <!-- 预设规则与默认负向词展开区 -->
          <div
            v-if="expandedPresetIds.has(p.id)"
            class="mt-2.5 rounded-lg border border-line/60 bg-canvas/50 p-2.5 text-xs space-y-2"
          >
            <div v-if="p.system_rules">
              <span class="text-[10px] font-medium text-muted uppercase">提示词润色增强规则 (System Rules)</span>
              <p class="mt-0.5 whitespace-pre-wrap font-sans text-xs text-ink/90 leading-relaxed">{{ p.system_rules }}</p>
            </div>
            <div v-if="p.default_params?.negative_prompt">
              <span class="text-[10px] font-medium text-muted uppercase">默认注入负向提示词 (Negative Prompt)</span>
              <p class="mt-0.5 font-mono text-[11px] text-rose-800 bg-rose-50/80 p-1.5 rounded border border-rose-200/50">{{ p.default_params.negative_prompt }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 添加/编辑创作预设抽屉 -->
      <div
        v-if="showAddPreset"
        class="mt-3 rounded-xl border border-line bg-canvas/50 p-4 space-y-3"
      >
        <div class="flex items-center justify-between border-b border-line/60 pb-2">
          <h5 class="text-xs font-semibold text-ink">
            {{ editingPresetId ? "编辑创作风格预设" : "添加自定义创作风格预设" }}
          </h5>
          <button class="text-xs text-muted hover:text-ink" @click="showAddPreset = false">取消</button>
        </div>

        <div class="space-y-2.5 text-xs">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-medium text-ink/80 mb-1">预设风格名称 *</label>
              <input
                v-model="presetForm.name"
                type="text"
                placeholder="例如：赛博朋克光影 / 复古胶片人像"
                class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
              />
            </div>
            <div>
              <label class="block text-[11px] font-medium text-ink/80 mb-1">适用创作模式</label>
              <AppleSelect
                v-model="presetForm.creation_mode"
                :options="creationModeOptions"
              />
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-medium text-ink/80 mb-1">英文标识 Code（选填）</label>
              <input
                v-model="presetForm.code"
                type="text"
                placeholder="例如：cyberpunk_glow"
                class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
              />
            </div>
            <div>
              <label class="block text-[11px] font-medium text-ink/80 mb-1">风格简要描述</label>
              <input
                v-model="presetForm.description"
                type="text"
                placeholder="简述该风格的视觉特色"
                class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent"
              />
            </div>
          </div>

          <div>
            <label class="block text-[11px] font-medium text-ink/80 mb-1">提示词润色规则 (System Rules)</label>
            <textarea
              v-model="presetForm.system_rules"
              rows="3"
              placeholder="定义大模型如何将简单词语润色为具有该风格专业质感的详细英文/中文提示词…"
              class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-accent leading-relaxed"
            />
          </div>

          <div>
            <label class="block text-[11px] font-medium text-ink/80 mb-1">默认负向提示词 (Negative Prompt)</label>
            <input
              v-model="presetForm.negative_prompt"
              type="text"
              placeholder="例如：blurry, low quality, deformed hands, bad anatomy"
              class="w-full rounded-md border border-line bg-white px-2.5 py-1.5 font-mono text-xs text-ink outline-none focus:border-accent"
            />
          </div>

          <p v-if="presetFormError" class="text-[11px] text-rose-600">{{ presetFormError }}</p>

          <div class="flex justify-end gap-2 pt-2 border-t border-line/60">
            <button
              type="button"
              class="rounded-md border border-line bg-white px-3 py-1 text-xs text-ink hover:bg-canvas transition"
              @click="showAddPreset = false"
            >
              取消
            </button>
            <button
              type="button"
              class="rounded-md bg-accent px-3 py-1 text-xs font-medium text-white hover:bg-accent/90 transition disabled:opacity-50"
              :disabled="savingPreset"
              @click="handleSavePreset"
            >
              {{ savingPreset ? "正在保存…" : editingPresetId ? "保存修改" : "保存预设" }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
