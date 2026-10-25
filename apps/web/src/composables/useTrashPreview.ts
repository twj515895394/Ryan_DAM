import { computed, ref } from "vue";

import { library, permanentlyDeleteTrashItem, restoreFromTrash } from "../stores/library";

import type { AssetOut, TrashItem } from "../api/types";
import type { ConfirmRequest } from "./useConfirmDialog";

/** TrashItem → AssetOut 预览投影：回收站元数据不含的字段以安全默认值填充。 */
function toAssetPreviewModel(item: TrashItem): AssetOut {
  return {
    id: item.id,
    folder_id: null,
    name: item.name,
    extension: item.extension ?? null,
    asset_type: item.asset_type,
    size_bytes: item.size_bytes,
    source_type: item.source_type,
    thumbnail_status: item.thumbnail_status ?? "none",
    status: "trashed",
    media_width: item.media_width ?? null,
    media_height: item.media_height ?? null,
    media_duration_ms: item.media_duration_ms ?? null,
    file_path: "",
    created_at: item.created_at ?? item.deleted_at ?? "",
    updated_at: item.updated_at ?? item.deleted_at ?? "",
    tags: [],
    has_prompt: false
  };
}

/**
 * 回收站沉浸式预览：以 id（而非下标）持有当前预览项，列表刷新后自动重定位；
 * 恢复/永久删除成功后前进到相邻项，回收站清空时自动关闭。
 */
export function useTrashPreview(ask: (request: ConfirmRequest) => void) {
  const trashPreviewId = ref<number | null>(null);

  const trashPreviewItem = computed<TrashItem | null>(() => {
    if (trashPreviewId.value === null) return null;
    return library.trash.find((t) => t.id === trashPreviewId.value) ?? null;
  });

  const trashPreviewAsset = computed<AssetOut | null>(() =>
    trashPreviewItem.value ? toAssetPreviewModel(trashPreviewItem.value) : null
  );

  function openTrashPreview(item: TrashItem): void {
    trashPreviewId.value = item.id;
  }

  function closeTrashPreview(): void {
    trashPreviewId.value = null;
  }

  /** 环绕步进预览（首尾相接，与画廊预览一致）。 */
  function stepTrashPreview(delta: number): void {
    const list = library.trash;
    if (trashPreviewId.value === null || list.length === 0) return;
    const index = list.findIndex((t) => t.id === trashPreviewId.value);
    if (index < 0) return;
    const count = list.length;
    trashPreviewId.value = list[((index + delta) % count + count) % count].id;
  }

  /** 当前项被移除后的邻居 id（在异步操作前计算，列表刷新后 prev/next 指向一致）。 */
  function neighborId(removedId: number): number | null {
    const list = library.trash;
    const index = list.findIndex((t) => t.id === removedId);
    if (index < 0) return null;
    const count = list.length;
    if (count <= 1) return null;
    const nextIndex = index + 1 < count ? index + 1 : 0;
    return list[nextIndex].id;
  }

  function advanceAfterRemoval(removedId: number, ok: boolean): void {
    if (!ok || trashPreviewId.value !== removedId) return;
    trashPreviewId.value = neighborId(removedId);
  }

  function restoreTrashItem(item: TrashItem): void {
    const target = item.id;
    void restoreFromTrash(target).then((ok) => advanceAfterRemoval(target, ok));
  }

  function askPermanentDeleteTrashItem(item: TrashItem): void {
    const target = item.id;
    ask({
      title: "永久删除该资产？",
      description: `确定永久删除「${item.name}」吗？\n文件将从磁盘中彻底删除，此操作不可恢复。`,
      confirmText: "永久删除",
      intent: "danger",
      action: () => {
        void permanentlyDeleteTrashItem(target).then((ok) => advanceAfterRemoval(target, ok));
      }
    });
  }

  return {
    trashPreviewItem,
    trashPreviewAsset,
    openTrashPreview,
    closeTrashPreview,
    stepTrashPreview,
    restoreTrashItem,
    askPermanentDeleteTrashItem
  };
}
