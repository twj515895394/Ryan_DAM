import { computed } from "vue";
import { library } from "../stores/library";
import type { FolderNode } from "../api/types";

export interface MoveFolderOption {
  id: number;
  label: string;
  name: string;
}

export interface MoveFolderGroup {
  id: string;
  label: string;
  options: MoveFolderOption[];
}

// ── 树形目标选择器（TargetFolderDialog / FolderPickerTree）共用节点 ──
export interface FolderPickerNode {
  /** "general" | `project:<id>` | `folder:<id>` */
  key: string;
  label: string;
  icon?: "folder" | "project";
  disabled?: boolean;
  children?: FolderPickerNode[];
}

/** 库内目录树 → 选择器节点（folder:<id>）。 */
export function toPickerNodes(nodes: FolderNode[]): FolderPickerNode[] {
  return nodes.map((node) => ({
    key: `folder:${node.id}`,
    label: node.name,
    children: toPickerNodes(node.children)
  }));
}

export function flattenFolderNodes(
  nodes: FolderNode[],
  prefix: string,
  out: MoveFolderOption[]
): void {
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.name}` : node.name;
    out.push({ id: node.id, label, name: node.name });
    flattenFolderNodes(node.children, label, out);
  }
}

export function useFolderOptions() {
  const allFolderGroups = computed<MoveFolderGroup[]>(() => {
    const groups: MoveFolderGroup[] = [];

    // 1. 通用资产库
    const generalOptions: MoveFolderOption[] = [];
    flattenFolderNodes(library.generalTree, "", generalOptions);
    if (generalOptions.length > 0) {
      groups.push({
        id: "general",
        label: "通用资产库",
        options: generalOptions
      });
    }

    // 2. 各个项目
    for (const project of library.projects) {
      const projTree = library.projectTrees[project.id] ?? [];
      const projOptions: MoveFolderOption[] = [];
      flattenFolderNodes(projTree, "", projOptions);
      if (projOptions.length > 0) {
        groups.push({
          id: `project-${project.id}`,
          label: `项目：${project.name}`,
          options: projOptions
        });
      }
    }

    return groups;
  });

  const allFolderOptions = computed<MoveFolderOption[]>(() => {
    return allFolderGroups.value.flatMap((g) => g.options);
  });

  return {
    allFolderGroups,
    allFolderOptions,
    flattenFolderNodes
  };
}
