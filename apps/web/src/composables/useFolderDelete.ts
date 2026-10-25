import { api } from "../api/client";
import { deleteFolder } from "../stores/library";

import type { FolderNode } from "../api/types";
import type { ConfirmRequest } from "./useConfirmDialog";

/**
 * Apple HIG 目录删除确认流：先异步拉取目录统计（GET /folders/{id}/stats），
 * 空目录给出轻量确认；含内容时明确列出子目录与资产影响（托管→回收站、外部→仅移除索引），
 * 确认后调用级联删除。统计接口失败时降级为默认级联确认，绝不静默删除。
 */
export function useFolderDelete(ask: (request: ConfirmRequest) => void) {
  function askDeleteFolder(node: FolderNode, afterDeleted: (ok: boolean) => void): void {
    void buildAndAsk(node, afterDeleted);
  }

  async function buildAndAsk(node: FolderNode, afterDeleted: (ok: boolean) => void): Promise<void> {
    // 锁定前置拦截：侧栏已禁用删除按钮，此处兜底树刷新竞态（后端 409 仍是最终事实源）
    if (node.locked) {
      ask({
        title: "文件夹已锁定",
        description: `「${node.name}」处于锁定状态，无法删除。\n请在该目录的「编辑文件夹」弹窗中解除锁定后再试。`,
        confirmText: "知道了",
        intent: "warning",
        action: () => {}
      });
      return;
    }
    try {
      const stats = await api.getFolderStats(node.id);
      const hasContents = stats.subfolder_count > 0 || stats.asset_count > 0;

      if (!hasContents) {
        ask({
          title: "删除文件夹？",
          description: `确定删除空文件夹「${node.name}」吗？`,
          confirmText: "删除文件夹",
          intent: "danger",
          action: () => {
            void deleteFolder(node.id, false).then(afterDeleted);
          }
        });
        return;
      }

      const detailParts: string[] = [];
      if (stats.subfolder_count > 0) detailParts.push(`${stats.subfolder_count} 个子文件夹`);
      if (stats.asset_count > 0) detailParts.push(`${stats.asset_count} 个资产`);

      const consequenceParts: string[] = [];
      if (stats.managed_asset_count > 0) {
        consequenceParts.push(`${stats.managed_asset_count} 个托管资产将移入回收站`);
      }
      if (stats.external_asset_count > 0) {
        consequenceParts.push(`${stats.external_asset_count} 个外部素材将移除索引（源文件保留）`);
      }

      ask({
        title: "级联删除文件夹？",
        description:
          `确定删除文件夹「${node.name}」及其全部内容吗？\n\n` +
          `包含：${detailParts.join("、")}\n` +
          `操作影响：${consequenceParts.join("，")}，所有子文件夹将被级联删除。`,
        confirmText: "级联删除",
        intent: "danger",
        action: () => {
          void deleteFolder(node.id, true).then(afterDeleted);
        }
      });
    } catch {
      // 统计失败降级为默认级联确认，保证用户始终看到明确的破坏性操作说明
      ask({
        title: "删除文件夹？",
        description: `确定删除文件夹「${node.name}」吗？其内的托管资产将移入回收站，外部素材仅移除索引。`,
        confirmText: "删除文件夹",
        intent: "danger",
        action: () => {
          void deleteFolder(node.id, true).then(afterDeleted);
        }
      });
    }
  }

  return { askDeleteFolder };
}
