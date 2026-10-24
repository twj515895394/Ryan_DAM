import { reactive } from "vue";

import { api, ApiRequestError } from "../api/client";
import type { FolderNode, Project, Settings } from "../api/types";

export interface LibraryState {
  loaded: boolean;
  generalTree: FolderNode[];
  projects: Project[];
  projectTrees: Record<number, FolderNode[]>;
  settings: Settings | null;
  notice: { kind: "error" | "success"; text: string } | null;
}

export const library = reactive<LibraryState>({
  loaded: false,
  generalTree: [],
  projects: [],
  projectTrees: {},
  settings: null,
  notice: null
});

let noticeTimer: ReturnType<typeof setTimeout> | null = null;

export function notify(kind: "error" | "success", text: string): void {
  library.notice = { kind, text };
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    library.notice = null;
  }, 5000);
}

export function errText(error: unknown): string {
  if (error instanceof ApiRequestError) return error.message;
  return error instanceof Error ? error.message : String(error);
}

export async function loadAll(): Promise<void> {
  try {
    const [generalTree, projects, settings] = await Promise.all([
      api.generalTree(),
      api.listProjects(),
      api.getSettings()
    ]);
    library.generalTree = generalTree;
    library.projects = projects;
    library.settings = settings;
    const trees = await Promise.all(projects.map((p) => api.projectTree(p.id)));
    const projectTrees: Record<number, FolderNode[]> = {};
    projects.forEach((p, index) => {
      projectTrees[p.id] = trees[index];
    });
    library.projectTrees = projectTrees;
    library.loaded = true;
  } catch (error) {
    notify("error", errText(error));
  }
}

export async function createProject(name: string): Promise<boolean> {
  try {
    await api.createProject(name);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function renameProject(id: number, name: string): Promise<boolean> {
  try {
    await api.renameProject(id, name);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function deleteProject(id: number): Promise<boolean> {
  try {
    await api.deleteProject(id);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function createGeneralFolder(name: string, parentId: number | null): Promise<boolean> {
  try {
    await api.createFolder({ name, scope: "general", parent_id: parentId });
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function createProjectFolder(projectId: number, name: string, parentId: number | null): Promise<boolean> {
  try {
    await api.createFolder({ name, scope: "project", project_id: projectId, parent_id: parentId });
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function renameFolder(id: number, name: string): Promise<boolean> {
  try {
    await api.renameFolder(id, name);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function deleteFolder(id: number): Promise<boolean> {
  try {
    await api.deleteFolder(id);
    await loadAll();
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}

export async function updateManagedRoot(path: string): Promise<boolean> {
  try {
    library.settings = await api.updateSettings(path);
    notify("success", "默认存储位置已更新（只影响之后的导入）。");
    return true;
  } catch (error) {
    notify("error", errText(error));
    return false;
  }
}
