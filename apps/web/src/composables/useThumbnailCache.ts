/**
 * 缩略图 object URL 的模块级共享缓存 + 组件加载 composable。
 *
 * 此前 AssetCard / TrashRowThumb 每次挂载都带 token 重新抓取 blob、卸载即 revoke，
 * 虚拟滚动、目录切换、回收站往返都会对同一资产重复请求 /thumbnail。这里把成功结果
 * 以 LRU 形式长期持有（上限 240 条 ≈ 最坏 ~30MB JPEG），重挂载的卡片直接复用；
 * thumbnail_status=failed 的资产记为负结果，避免反复 404，状态离开 failed 时清除。
 *
 * 已知取舍：源文件被替换且后端重新生成缩略图后，缓存条目会显示旧图，直到该条目被
 * LRU 逐出或前端刷新；512px 预览场景下可接受。
 */

import { onScopeDispose, shallowRef, watch, type ShallowRef } from "vue";

import { api } from "../api/client";

const MAX_ENTRIES = 240;

/** 插入顺序即 LRU 顺序：命中后 delete+set 移到末尾，逐出取队首。 */
const urls = new Map<number, string>();
const failedIds = new Set<number>();

function getCached(assetId: number): string | null {
  const url = urls.get(assetId);
  if (url === undefined) return null;
  urls.delete(assetId);
  urls.set(assetId, url);
  return url;
}

function putCached(assetId: number, url: string): void {
  const stale = urls.get(assetId);
  urls.delete(assetId);
  if (stale !== undefined && stale !== url) {
    URL.revokeObjectURL(stale); // 旧代 URL 不再被任何卡片引用（同 id 重载即状态变化）
  }
  urls.set(assetId, url);
  failedIds.delete(assetId);
  while (urls.size > MAX_ENTRIES) {
    const oldest = urls.keys().next();
    if (oldest.done) break;
    const evicted = urls.get(oldest.value);
    urls.delete(oldest.value);
    if (evicted) URL.revokeObjectURL(evicted);
  }
}

/**
 * 加载资产缩略图，返回可直接绑定 `<img :src>` 的 object URL（缓存持有，勿自行 revoke）。
 * getters 保持对 props 的响应式跟踪；组件卸载仅作废在途请求，不释放共享 URL。
 */
export function useThumbnailObjectUrl(
  assetId: () => number,
  assetType: () => string | null | undefined,
  thumbnailStatus: () => string | null | undefined
): ShallowRef<string | null> {
  const objectUrl = shallowRef<string | null>(null);
  let loadToken = 0;

  async function load(): Promise<void> {
    const type = assetType();
    const status = thumbnailStatus();
    const fetchable =
      type === "image" || type === "video" || (type === "audio" && status === "ready");
    if (!fetchable) {
      objectUrl.value = null;
      return;
    }
    const id = assetId();
    const cached = getCached(id);
    if (cached) {
      objectUrl.value = cached;
      return;
    }
    if (failedIds.has(id)) {
      objectUrl.value = null;
      return;
    }
    const token = ++loadToken;
    try {
      const url = await api.fetchThumbnailObjectUrl(id);
      putCached(id, url); // 迟到的成功结果同样入缓存，供下次挂载直接命中
      if (token === loadToken) objectUrl.value = url;
    } catch {
      if (token !== loadToken) return;
      // 仅「生成失败」是值得长期记住的负结果；pending 会随状态迁移由 watch 重试。
      if (thumbnailStatus() === "failed") failedIds.add(id);
      objectUrl.value = null;
    }
  }

  watch(
    () => [assetId(), thumbnailStatus()],
    () => {
      // 状态离开 failed（后端重试成功 / 源文件变更）：清除负结果，恢复正常加载。
      if (thumbnailStatus() !== "failed") failedIds.delete(assetId());
      void load();
    },
    { immediate: true }
  );

  onScopeDispose(() => {
    loadToken += 1; // 作废在途请求；URL 归缓存持有，这里绝不 revoke
  });

  return objectUrl;
}

/** 测试与调试辅助：清空全部缓存状态。 */
export function __resetThumbnailCache(): void {
  for (const url of urls.values()) URL.revokeObjectURL(url);
  urls.clear();
  failedIds.clear();
}
