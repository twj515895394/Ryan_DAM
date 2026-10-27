import { ref } from "vue";
import { api } from "../api/client";
import { notify } from "../stores/library";
import type { AiResult, AiResultWithTask, AiTaskDetail, AiTaskSummary, AssetOut } from "../api/types";
import type { SelectedReferenceItem } from "../components/AiReferencePickerModal.vue";

export function useAiWorkbench() {
  const showAiWorkbench = ref(false);
  const showAiTaskCenter = ref(false);
  const showAiBatchReverse = ref(false);
  const showAiHistory = ref(false);

  const workbenchInitialPrompt = ref("");
  const workbenchInitialRefIds = ref<number[]>([]);
  const workbenchInitialMode = ref<"image_generate" | "image_edit">("image_generate");
  const workbenchInitialModelId = ref<number | undefined>(undefined);
  const workbenchInitialPresetId = ref<number | undefined>(undefined);
  const workbenchInitialParams = ref<Record<string, any> | undefined>(undefined);
  const workbenchInitialReferences = ref<SelectedReferenceItem[] | undefined>(undefined);
  const workbenchInitialRetryOf = ref<string | undefined>(undefined);

  function resetWorkbenchState(): void {
    workbenchInitialPrompt.value = "";
    workbenchInitialRefIds.value = [];
    workbenchInitialMode.value = "image_generate";
    workbenchInitialModelId.value = undefined;
    workbenchInitialPresetId.value = undefined;
    workbenchInitialParams.value = undefined;
    workbenchInitialReferences.value = undefined;
    workbenchInitialRetryOf.value = undefined;
  }

  function openWorkbench(): void {
    resetWorkbenchState();
    showAiWorkbench.value = true;
  }

  function closeWorkbench(): void {
    showAiWorkbench.value = false;
    resetWorkbenchState();
  }

  async function openWorkbenchFromAsset(asset: AssetOut): Promise<void> {
    resetWorkbenchState();
    if (asset.has_prompt) {
      try {
        const p = await api.getAssetPrompt(asset.id);
        workbenchInitialPrompt.value = p.prompt_text || "";
      } catch {
        // ignore
      }
    }
    workbenchInitialRefIds.value = [asset.id];
    workbenchInitialMode.value = "image_edit";
    showAiWorkbench.value = true;
  }

  async function openWorkbenchVariant(task: AiTaskSummary | AiTaskDetail): Promise<void> {
    resetWorkbenchState();
    workbenchInitialPrompt.value = task.prompt_final || "";
    workbenchInitialMode.value = task.task_type === "image_edit" ? "image_edit" : "image_generate";
    workbenchInitialModelId.value = task.model_profile_id || undefined;
    workbenchInitialRetryOf.value = task.id;

    let detail: AiTaskDetail | null = null;
    if ("params" in task && "references" in task) {
      detail = task as AiTaskDetail;
    } else {
      try {
        detail = await api.getAiTask(task.id);
      } catch (err) {
        console.error("加载任务详情失败:", err);
      }
    }

    if (detail) {
      workbenchInitialPresetId.value = detail.preset_id || undefined;
      workbenchInitialParams.value = detail.params || {};
      if (detail.references && detail.references.length > 0) {
        workbenchInitialReferences.value = detail.references.map((r) => ({
          source_kind: r.source_kind as any,
          source_id: r.source_id || "",
          name: `${r.source_kind === "asset" ? "资产" : r.source_kind === "history_result" ? "历史" : "本地"} #${r.source_id}`,
          preview_url:
            r.source_kind === "asset"
              ? `/api/v1/assets/${r.source_id}/thumbnail`
              : r.source_kind === "history_result"
              ? api.getAiResultContentUrl(r.source_id || "")
              : "",
          role: r.role || "reference"
        }));
      }
    }

    showAiTaskCenter.value = false;
    showAiWorkbench.value = true;
  }

  function openWorkbenchContinueEdit(res: AiResult, task: AiTaskDetail): void {
    resetWorkbenchState();
    workbenchInitialMode.value = "image_edit";
    workbenchInitialModelId.value = task.model_profile_id || undefined;
    workbenchInitialRetryOf.value = task.id;
    workbenchInitialReferences.value = [
      {
        source_kind: "history_result",
        source_id: res.id,
        name: `历史产物 #${res.id.slice(-6)}`,
        preview_url: api.getAiResultContentUrl(res.id),
        role: "reference"
      }
    ];
    showAiTaskCenter.value = false;
    showAiWorkbench.value = true;
  }

  function openAiHistory(): void {
    showAiHistory.value = true;
  }

  function closeAiHistory(): void {
    showAiHistory.value = false;
  }

  function openWorkbenchFromHistory(item: AiResultWithTask): void {
    resetWorkbenchState();
    workbenchInitialPrompt.value = item.task?.prompt_final || "";
    workbenchInitialMode.value = "image_generate";
    workbenchInitialReferences.value = [
      {
        source_kind: "history_result",
        source_id: item.id,
        name: `历史产物 #${item.id.slice(-6)}`,
        preview_url: api.getAiResultContentUrl(item.id),
        role: "reference"
      }
    ];
    showAiHistory.value = false;
    showAiWorkbench.value = true;
  }

  function onAiTaskCreated(task: AiTaskSummary): void {
    notify("success", `AI 任务 #${task.id.slice(0, 8)} 已提交执行队列`);
    showAiTaskCenter.value = true;
  }

  return {
    showAiWorkbench,
    showAiTaskCenter,
    showAiBatchReverse,
    showAiHistory,
    workbenchInitialPrompt,
    workbenchInitialRefIds,
    workbenchInitialMode,
    workbenchInitialModelId,
    workbenchInitialPresetId,
    workbenchInitialParams,
    workbenchInitialReferences,
    workbenchInitialRetryOf,
    openWorkbench,
    closeWorkbench,
    openAiHistory,
    closeAiHistory,
    openWorkbenchFromHistory,
    openWorkbenchFromAsset,
    openWorkbenchVariant,
    openWorkbenchContinueEdit,
    onAiTaskCreated
  };
}
