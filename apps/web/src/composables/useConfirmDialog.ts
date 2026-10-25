import { ref } from "vue";

import type { ConfirmIntent } from "../components/ConfirmDialog.vue";

export interface ConfirmRequest {
  title: string;
  description: string;
  confirmText: string;
  intent: ConfirmIntent;
  action: () => void;
}

/** 全局 Apple HIG 确认弹窗状态机：ask() 打开，resolve/dismiss 收敛，action 在关闭后执行。 */
export function useConfirmDialog() {
  const confirmDialog = ref<ConfirmRequest | null>(null);

  function ask(request: ConfirmRequest): void {
    confirmDialog.value = request;
  }

  function resolveConfirm(): void {
    const action = confirmDialog.value?.action;
    confirmDialog.value = null;
    action?.();
  }

  function dismissConfirm(): void {
    confirmDialog.value = null;
  }

  return { confirmDialog, ask, resolveConfirm, dismissConfirm };
}
