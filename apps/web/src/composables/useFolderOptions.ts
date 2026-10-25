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
