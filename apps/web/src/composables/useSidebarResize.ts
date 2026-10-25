import { ref, type Ref } from "vue";

export const SIDEBAR_MIN_WIDTH = 220;
export const SIDEBAR_MAX_WIDTH = 480;
export const SIDEBAR_DEFAULT_WIDTH = 256;
const STORAGE_KEY = "ryan-dam-sidebar-width";
const KEYBOARD_STEP = 16;

function clampWidth(width: number): number {
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, width));
}

function readStoredWidth(): number {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw === null ? NaN : Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? clampWidth(parsed) : SIDEBAR_DEFAULT_WIDTH;
  } catch {
    return SIDEBAR_DEFAULT_WIDTH;
  }
}

/**
 * 侧栏可拖拽宽度（Apple 流体交互：指针 1:1 跟手、边界软钳制、可随时打断）。
 * 拖拽期间只改布局根节点的 `--sidebar-w` CSS 变量（不经过响应式状态），
 * 保证每帧零 Vue 重渲染；松手才持久化 localStorage。
 * 键盘 ←/→ 步进 16px、Home 复位默认宽度，双击复位，作为指针操作的等价替代。
 */
export function useSidebarResize(layoutEl: Ref<HTMLElement | null>) {
  const initialWidth = ref(readStoredWidth());
  let current = initialWidth.value;

  function applyWidth(px: number): void {
    current = clampWidth(px);
    layoutEl.value?.style.setProperty("--sidebar-w", `${current}px`);
  }

  function commit(): void {
    initialWidth.value = current;
    try {
      localStorage.setItem(STORAGE_KEY, String(current));
    } catch {
      // 隐私模式等写入失败可忽略：宽度仅本会话内存生效
    }
  }

  function onPointerDown(event: PointerEvent): void {
    event.preventDefault();
    const target = event.currentTarget as HTMLElement | null;
    const startX = event.clientX;
    const startWidth = current;
    try {
      target?.setPointerCapture(event.pointerId);
    } catch {
      // 合成事件无活动指针时忽略，window 级监听已覆盖跟踪
    }
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMove = (moveEvent: PointerEvent) => applyWidth(startWidth + (moveEvent.clientX - startX));
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      commit();
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }

  function onKeyDown(event: KeyboardEvent): void {
    if (event.key === "ArrowLeft") {
      applyWidth(current - KEYBOARD_STEP);
      commit();
    } else if (event.key === "ArrowRight") {
      applyWidth(current + KEYBOARD_STEP);
      commit();
    } else if (event.key === "Home") {
      applyWidth(SIDEBAR_DEFAULT_WIDTH);
      commit();
    } else {
      return;
    }
    event.preventDefault();
  }

  function onDoubleClick(): void {
    applyWidth(SIDEBAR_DEFAULT_WIDTH);
    commit();
  }

  return { initialWidth, onPointerDown, onKeyDown, onDoubleClick };
}
