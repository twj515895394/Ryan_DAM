import { ref } from "vue";
import { api } from "../api/client";
import type { PromptOptimizeResult } from "../api/types";

export function usePromptOptimize() {
  const optimizing = ref(false);
  const optimizeError = ref("");
  const lastOptimizedResult = ref<PromptOptimizeResult | null>(null);
  const originalPromptBeforeOpt = ref<string | null>(null);

  async function optimizePrompt(
    currentPrompt: string,
    presetId: number | null
  ): Promise<string | null> {
    if (!currentPrompt.trim() || optimizing.value) return null;
    optimizing.value = true;
    optimizeError.value = "";
    originalPromptBeforeOpt.value = currentPrompt;

    try {
      const res = await api.optimizePrompt({
        prompt: currentPrompt,
        preset_id: presetId,
        model_profile_id: undefined
      });
      lastOptimizedResult.value = res;
      return res.optimized_prompt;
    } catch (err: any) {
      optimizeError.value = err.message || "提示词润色失败，请确认已配置 text_optimize 默认模型";
      return null;
    } finally {
      optimizing.value = false;
    }
  }

  function revertOptimization(): string | null {
    if (originalPromptBeforeOpt.value !== null) {
      const original = originalPromptBeforeOpt.value;
      lastOptimizedResult.value = null;
      originalPromptBeforeOpt.value = null;
      return original;
    }
    return null;
  }

  function resetOptimizeState(): void {
    optimizing.value = false;
    optimizeError.value = "";
    lastOptimizedResult.value = null;
    originalPromptBeforeOpt.value = null;
  }

  return {
    optimizing,
    optimizeError,
    lastOptimizedResult,
    originalPromptBeforeOpt,
    optimizePrompt,
    revertOptimization,
    resetOptimizeState
  };
}
