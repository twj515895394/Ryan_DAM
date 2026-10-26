import { computed, ref, type ComputedRef, type Ref } from "vue";
import { toPickerNodes, type FolderPickerNode } from "./useFolderOptions";
import type { ConfirmRequest } from "./useConfirmDialog";
import type { ExternalSource } from "../api/types";
import {
  ensureTopLevelFolder,
  importFiles,
  importFolder,
  library,
  linkExternalSource,
  unlinkExternalSource
} from "../stores/library";

export type TargetDialogRequest =
  | { kind: "external-link"; root: string }
  | { kind: "import-files" }
  | { kind: "import-folder" };

export interface UseImportFlowOptions {
  activeScope: Ref<"general" | "project">;
  activeProjectId: Ref<number | null>;
  activeFolderId: Ref<number | null>;
  ask: (request: ConfirmRequest) => void;
}

export function useImportFlow({
  activeScope,
  activeProjectId,
  activeFolderId,
  ask
}: UseImportFlowOptions) {
  const targetDialog = ref<TargetDialogRequest | null>(null);

  const canImport = computed(
    () => !["queued", "running"].includes(library.importJob?.status ?? "")
  );

  async function runFilesImport(folderId: number): Promise<void> {
    let paths: string[] = [];
    try {
      paths = await window.ryanDam.selectFiles();
    } catch {
      return;
    }
    if (paths.length === 0) return;
    await importFiles(paths, folderId);
  }

  async function runFolderImport(folderId: number): Promise<void> {
    let folder: string | null = null;
    try {
      folder = await window.ryanDam.selectFolder();
    } catch {
      return;
    }
    if (!folder) return;
    await importFolder(folder, folderId);
  }

  function getFolderNameFromPath(dirPath: string): string {
    const normalized = dirPath.replace(/[/\\]+$/, "");
    const parts = normalized.split(/[/\\]/);
    return parts[parts.length - 1] || "新建文件夹";
  }

  function startImport(): void {
    if (activeFolderId.value !== null) {
      void runFilesImport(activeFolderId.value);
      return;
    }
    targetDialog.value = { kind: "import-files" };
  }

  async function startFolderImport(): Promise<void> {
    if (activeFolderId.value !== null) {
      await runFolderImport(activeFolderId.value);
      return;
    }
    let folderPath: string | null = null;
    try {
      folderPath = await window.ryanDam.selectFolder();
    } catch {
      return;
    }
    if (!folderPath) return;

    const folderName = getFolderNameFromPath(folderPath);
    const scope = activeScope.value === "project" ? "project" : "general";
    const projectId = scope === "project" ? activeProjectId.value : null;

    const targetFolder = await ensureTopLevelFolder(scope, folderName, projectId);
    if (!targetFolder) return;
    await importFolder(folderPath, targetFolder.id);
  }

  async function startLinkExternal(): Promise<void> {
    let folder: string | null = null;
    try {
      folder = await window.ryanDam.selectFolder();
    } catch {
      return;
    }
    if (!folder) return;
    targetDialog.value = { kind: "external-link", root: folder };
  }

  async function onTargetDialogConfirm(key: string, createMountFolder: boolean): Promise<void> {
    const request = targetDialog.value;
    targetDialog.value = null;
    if (!request) return;
    if (request.kind === "external-link") {
      if (key === "general") await linkExternalSource(request.root, { createMountFolder });
      else if (key.startsWith("project:"))
        await linkExternalSource(request.root, { targetProjectId: Number(key.slice(8)), createMountFolder });
      else await linkExternalSource(request.root, { targetFolderId: Number(key.slice(7)), createMountFolder });
      return;
    }
    const folderId = Number(key.slice(7));
    if (request.kind === "import-files") await runFilesImport(folderId);
    else await runFolderImport(folderId);
  }

  async function createAndPickFolder(name: string): Promise<void> {
    const scope = activeScope.value === "project" ? "project" : "general";
    const projectId = scope === "project" ? activeProjectId.value : null;

    const folder = await ensureTopLevelFolder(scope, name, projectId);
    if (!folder) return;
    // 导入流程：直接落到新建的顶层目录（无外部关联挂载语义）
    await onTargetDialogConfirm(`folder:${folder.id}`, false);
  }

  function askUnlinkExternal(source: ExternalSource): void {
    ask({
      title: "解除外部目录关联？",
      description:
        `确定解除关联「${source.display_name ?? source.root_path}」吗？\n\n` +
        `将移除该来源下 ${source.asset_count} 个外部资产索引（含 ${source.missing_count} 个失效项）；` +
        `不会删除磁盘上的源文件；已转为托管的资产不受影响。`,
      confirmText: "解除关联",
      intent: "warning",
      action: () => {
        void unlinkExternalSource(source.id);
      }
    });
  }

  const targetDialogRoots: ComputedRef<FolderPickerNode[]> = computed(() => {
    const kind = targetDialog.value?.kind;
    if (!kind) return [];
    if (kind === "external-link") {
      // 任意节点可选：通用资产库 / 各项目顶层，或任意已有目录
      return [
        { key: "general", label: "通用资产库", children: toPickerNodes(library.generalTree) },
        ...library.projects.map((project) => ({
          key: `project:${project.id}`,
          label: project.name,
          icon: "project" as const,
          children: toPickerNodes(library.projectTrees[project.id] ?? [])
        }))
      ];
    }
    // 导入对话框限定在通用/当前项目范围
    if (activeScope.value === "general") return toPickerNodes(library.generalTree);
    return toPickerNodes(library.projectTrees[activeProjectId.value ?? -1] ?? []);
  });

  return {
    targetDialog,
    canImport,
    startImport,
    startFolderImport,
    createAndPickFolder,
    startLinkExternal,
    onTargetDialogConfirm,
    askUnlinkExternal,
    targetDialogRoots
  };
}
