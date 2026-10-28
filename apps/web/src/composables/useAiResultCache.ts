/**
 * AI 生成结果产物 (AiResult) 图像 Object URL 的模块级共享 LRU 缓存与加载 Composable。
 *
 * 解决问题：
 * 1. 本地 FastAPI 后端受 local_api_guard 保护，原生 <img :src> 无法附带 X-Ryan-DAM-Token 请求头导致 401 裂图。
 * 2. 避免多次渲染同一 AI 产物时重复发起 HTTP 下载与重复占用内存。
 * 3. 统一管理 URL.createObjectURL 与 URL.revokeObjectURL 声明周期，杜绝内存泄漏。
 */

import { onScopeDispose, shallowRef, watch, type ShallowRef } from "vue";
import { api } from "../api/client";

const MAX_ENTRIES = 160;

/** 插入顺序即 LRU 顺序：命中后 delete+set 移到末尾，逐出取队首 */
const urls = new Map<string, string>();
const inFlight = new Map<string, Promise<string>>();
const failedIds = new Set<string>();

export function getCachedAiResultUrl(resultId: string): string | null {
  const url = urls.get(resultId);
  if (url === undefined) return null;
  urls.delete(resultId);
  urls.set(resultId, url);
  return url;
}

export function putCachedAiResultUrl(resultId: string, url: string): void {
  const stale = urls.get(resultId);
  urls.delete(resultId);
  if (stale !== undefined && stale !== url) {
    URL.revokeObjectURL(stale);
  }
  urls.set(resultId, url);
  failedIds.delete(resultId);

  while (urls.size > MAX_ENTRIES) {
    const oldest = urls.keys().next();
    if (oldest.done) break;
    const evicted = urls.get(oldest.value);
    urls.delete(oldest.value);
    if (evicted) URL.revokeObjectURL(evicted);
  }
}

/**
 * 预加载或获取 AI 结果的 Object URL
 */
export async function loadAiResultObjectUrl(resultId: string): Promise<string | null> {
  if (!resultId) return null;
  const cached = getCachedAiResultUrl(resultId);
  if (cached) return cached;
  if (failedIds.has(resultId)) return null;

  const existingPromise = inFlight.get(resultId);
  if (existingPromise) return existingPromise;

  const p = api
    .fetchAiResultContentObjectUrl(resultId)
    .then((url) => {
      putCachedAiResultUrl(resultId, url);
      return url;
    })
    .catch((err) => {
      failedIds.add(resultId);
      console.warn(`[useAiResultCache] Failed to load image for result #${resultId}:`, err);
      return null;
    })
    .finally(() => {
      inFlight.delete(resultId);
    });

  inFlight.set(resultId, p as Promise<string>);
  return p;
}

/**
 * 加载单个 AI 产物大图或缩略图，返回可直接绑定 <img :src> 的 Object URL（缓存持有）。
 */
export function useAiResultObjectUrl(
  resultIdGetter: () => string | null | undefined
): ShallowRef<string | null> {
  const objectUrl = shallowRef<string | null>(null);
  let loadToken = 0;

  async function load(): Promise<void> {
    const currentToken = ++loadToken;
    const id = resultIdGetter();

    if (!id) {
      objectUrl.value = null;
      return;
    }

    const cached = getCachedAiResultUrl(id);
    if (cached) {
      objectUrl.value = cached;
      return;
    }

    if (failedIds.has(id)) {
      objectUrl.value = null;
      return;
    }

    const loaded = await loadAiResultObjectUrl(id);
    if (currentToken === loadToken) {
      objectUrl.value = loaded;
    }
  }

  watch(resultIdGetter, () => {
    void load();
  }, { immediate: true });

  onScopeDispose(() => {
    loadToken++;
  });

  return objectUrl;
}
