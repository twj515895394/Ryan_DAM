import { api } from "../api/client";
import { deleteProject } from "../stores/library";

import type { ConfirmRequest } from "./useConfirmDialog";

/**
 * Apple HIG 项目级联删除确认流：先异步拉取项目统计（GET /projects/{id}/stats），
 * 空项目给出轻量确认；含内容时明确列出子文件夹与资产影响
 * （托管→回收站、外部→仅移除索引），确认后调用级联删除。
 * 统计接口失败时降级为默认级联确认，绝不静默删除。
 */
export function useProjectDelete(ask: (request: ConfirmRequest) => void) {
  function askDeleteProject(projectId: number, name: string, afterDeleted: (ok: boolean) => void): void {
    void buildAndAsk(projectId, name, afterDeleted);
  }

  async function buildAndAsk(
    projectId: number,
    name: string,
    afterDeleted: (ok: boolean) => void
  ): Promise<void> {
    try {
      const stats = await api.getProjectStats(projectId);
      const hasContents = stats.subfolder_count > 0 || stats.asset_count > 0;

      if (!hasContents) {
        ask({
          title: "删除项目？",
          description: `确定删除空项目「${name}」吗？`,
          confirmText: "删除项目",
          intent: "danger",
          action: () => {
            void deleteProject(projectId, false).then(afterDeleted);
          }
        });
        return;
      }

      const detailParts: string[] = [];
      if (stats.subfolder_count > 0) detailParts.push(`${stats.subfolder_count} 个文件夹`);
      if (stats.asset_count > 0) detailParts.push(`${stats.asset_count} 个资产`);

      const consequenceParts: string[] = [];
      if (stats.managed_asset_count > 0) {
        consequenceParts.push(`${stats.managed_asset_count} 个托管资产将移入回收站`);
      }
      if (stats.external_asset_count > 0) {
        consequenceParts.push(`${stats.external_asset_count} 个外部素材将移除索引（源文件保留）`);
      }

      ask({
        title: "级联删除项目？",
        description:
          `确定删除项目「${name}」及其全部内容吗？\n\n` +
          `包含：${detailParts.join("、")}\n` +
          `操作影响：${consequenceParts.join("，") || "无资产受影响"}，所有文件夹与子文件夹将被级联删除。`,
        confirmText: "级联删除",
        intent: "danger",
        action: () => {
          void deleteProject(projectId, true).then(afterDeleted);
        }
      });
    } catch {
      // 统计失败降级为默认级联确认，保证用户始终看到明确的破坏性操作说明
      ask({
        title: "删除项目？",
        description: `确定删除项目「${name}」及其全部内容吗？其内的托管资产将移入回收站，外部素材仅移除索引。`,
        confirmText: "删除项目",
        intent: "danger",
        action: () => {
          void deleteProject(projectId, true).then(afterDeleted);
        }
      });
    }
  }

  return { askDeleteProject };
}
