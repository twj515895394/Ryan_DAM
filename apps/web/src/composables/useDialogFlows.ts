import { computed, ref } from "vue";

import {
  createGeneralFolder,
  createProject,
  createProjectFolder,
  createTag,
  library,
  renameAssetById,
  renameProject,
  renameTag,
  updateManagedRoot
} from "../stores/library";

export type DialogRequest =
  | { kind: "project-create" }
  | { kind: "project-rename"; projectId: number; initial: string }
  | { kind: "folder-create"; scope: "general" | "project"; projectId: number | null; parentId: number | null }
  | { kind: "tag-create" }
  | { kind: "tag-rename"; tagId: number; initial: string }
  | { kind: "asset-rename"; assetId: number; initial: string }
  | { kind: "root-edit" };

/**
 * 通用输入对话框（NameDialog）状态机：集中维护 DialogRequest 与标题/初值派生，
 * 确认时按类型分发到 store 动作；资产重命名成功后回调宿主以重定位预览。
 */
export function useDialogFlows(deps: { onAssetRenamed: (assetId: number) => void }) {
  const dialog = ref<DialogRequest | null>(null);

  const dialogTitle = computed(() => {
    const d = dialog.value;
    if (!d) return "";
    switch (d.kind) {
      case "project-create": return "新建项目";
      case "project-rename": return "重命名项目";
      case "folder-create": return d.parentId === null ? "新建顶层文件夹" : "新建子文件夹";
      case "tag-create": return "新建标签";
      case "tag-rename": return "重命名标签";
      case "asset-rename": return "重命名资产";
      case "root-edit": return "修改默认托管存储位置";
    }
  });

  const dialogInitial = computed(() => {
    const d = dialog.value;
    if (
      d?.kind === "project-rename" ||
      d?.kind === "tag-rename" ||
      d?.kind === "asset-rename"
    ) {
      return d.initial;
    }
    if (d?.kind === "root-edit") return library.settings?.managed_root ?? "";
    return "";
  });

  async function onDialogConfirm(value: string): Promise<void> {
    const d = dialog.value;
    if (!d) return;
    let ok = false;
    switch (d.kind) {
      case "project-create":
        ok = await createProject(value);
        break;
      case "project-rename":
        ok = await renameProject(d.projectId, value);
        break;
      case "folder-create":
        ok =
          d.scope === "general"
            ? await createGeneralFolder(value, d.parentId)
            : await createProjectFolder(d.projectId ?? -1, value, d.parentId);
        break;
      case "tag-create":
        ok = Boolean(await createTag(value));
        break;
      case "tag-rename":
        ok = await renameTag(d.tagId, value);
        break;
      case "asset-rename":
        ok = await renameAssetById(d.assetId, value);
        if (ok) deps.onAssetRenamed(d.assetId);
        break;
      case "root-edit":
        ok = await updateManagedRoot(value);
        break;
    }
    if (ok) dialog.value = null;
  }

  return { dialog, dialogTitle, dialogInitial, onDialogConfirm };
}
