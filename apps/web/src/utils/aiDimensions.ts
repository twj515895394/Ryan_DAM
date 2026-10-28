/**
 * AI 图像生成画幅比例与尺寸分辨率智能解析及匹配工具
 */

export const STANDARD_ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"] as const;
export type StandardAspectRatio = typeof STANDARD_ASPECT_RATIOS[number];

/**
 * 现代生图模型（如 FLUX.1、SDXL、DALL-E 3、Midjourney 等）通用分辨率库
 * 包含常见 720P、1080P 全高清、2K 极清等多种档位规格
 */
export const DEFAULT_AI_RESOLUTIONS = [
  // 1:1 正方形
  "1024x1024",
  "1536x1536",
  "2048x2048",
  // 16:9 宽屏横向
  "1280x720",
  "1344x768",
  "1792x1024",
  "1920x1080",
  "2560x1440",
  // 9:16 长屏纵向
  "720x1280",
  "768x1344",
  "1024x1792",
  "1080x1920",
  "1440x2560",
  // 4:3 经典横幅
  "1024x768",
  "1152x864",
  "1440x1080",
  "1600x1200",
  "2048x1536",
  // 3:4 肖像纵幅
  "768x1024",
  "864x1152",
  "1080x1440",
  "1200x1600",
  "1536x2048",
  // 21:9 电影超宽屏
  "1536x640",
  "2560x1080"
];

/**
 * 解析尺寸字符串为数字宽高 [width, height]
 * 支持 1280x720, 1024*1024, 768X1024 等格式
 */
export function parseDimensions(sizeStr: string | null | undefined): [number, number] | null {
  if (!sizeStr) return null;
  const parts = sizeStr.split(/[xX*]/).map((s) => Number(s.trim()));
  if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1]) && parts[0] > 0 && parts[1] > 0) {
    return [parts[0], parts[1]];
  }
  return null;
}

/**
 * 解析画幅比例字符串为浮点比值 (width / height)
 * 支持 16:9, 9:16, 1:1, 4/3 等格式
 */
export function parseRatio(ratioStr: string | null | undefined): number | null {
  if (!ratioStr) return null;
  const parts = ratioStr.split(/[:/]/).map((s) => Number(s.trim()));
  if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1]) && parts[0] > 0 && parts[1] > 0) {
    return parts[0] / parts[1];
  }
  return null;
}

/**
 * 判断指定尺寸是否符合目标画幅比例
 * 设置 6% 容差，包容如 1792x1024 (1.75 与 16:9 的 1.778 误差仅 1.5%)、1024x1792 等真实模型预设
 */
export function matchSizeRatio(sizeStr: string, ratioStr: string): boolean {
  const dim = parseDimensions(sizeStr);
  const targetRatio = parseRatio(ratioStr);
  if (!dim || targetRatio === null) return false;
  const actualRatio = dim[0] / dim[1];
  return Math.abs(actualRatio - targetRatio) / targetRatio <= 0.06;
}

/**
 * 从给定的候选比例列表中，寻找与指定尺寸最为接近的画幅比例
 */
export function findBestRatioForSize(
  sizeStr: string,
  candidateRatios: string[] = ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"]
): string | null {
  const dim = parseDimensions(sizeStr);
  if (!dim) return null;
  const actualRatio = dim[0] / dim[1];

  let bestRatio: string | null = null;
  let minDiff = Infinity;

  for (const r of candidateRatios) {
    const target = parseRatio(r);
    if (target === null) continue;
    const diff = Math.abs(actualRatio - target) / target;
    if (diff < minDiff && diff <= 0.08) {
      minDiff = diff;
      bestRatio = r;
    }
  }

  return bestRatio;
}

/**
 * 获取比例的人类可读简要说明
 */
export function getAspectRatioLabel(ratio: string): string {
  switch (ratio) {
    case "1:1":
      return "正方形";
    case "16:9":
      return "宽屏横向";
    case "9:16":
      return "长屏纵向";
    case "4:3":
      return "经典横幅";
    case "3:4":
      return "肖像纵幅";
    case "21:9":
      return "电影超宽屏";
    default:
      return "自定义画幅";
  }
}

/**
 * 获取比例的建议适用场景
 */
export function getAspectRatioHint(ratio: string): string {
  switch (ratio) {
    case "1:1":
      return "正方形 (头像/壁纸/社交配图)";
    case "16:9":
      return "宽屏横向 (桌面壁纸/视频封面)";
    case "9:16":
      return "长屏纵向 (手机海报/短视频封面)";
    case "4:3":
      return "经典横幅 (摄影相册/插画展示)";
    case "3:4":
      return "肖像纵幅 (单人人像/游戏立绘)";
    case "21:9":
      return "电影超宽屏 (全景风光/电影质感宽银幕)";
    default:
      return "按特定比例渲染";
  }
}

/**
 * 获取分辨率的智能描述与徽标标记
 */
export function getResolutionMeta(sizeStr: string): {
  subLabel: string;
  badge: string;
  badgeColor: "blue" | "rose" | "emerald" | "amber" | "zinc";
} {
  const dim = parseDimensions(sizeStr);
  if (!dim) {
    return { subLabel: "自定义规格", badge: "自定义", badgeColor: "zinc" };
  }
  const [w, h] = dim;
  const maxD = Math.max(w, h);

  if (w === 1920 && h === 1080) {
    return { subLabel: "1080P 全高清横屏 (16:9)", badge: "1080P", badgeColor: "blue" };
  }
  if (w === 1080 && h === 1920) {
    return { subLabel: "1080P 全高清竖屏 (9:16)", badge: "1080P", badgeColor: "rose" };
  }
  if (w === 2560 && h === 1440) {
    return { subLabel: "2K QHD 极清横屏 (16:9)", badge: "2K", badgeColor: "blue" };
  }
  if (w === 1440 && h === 2560) {
    return { subLabel: "2K 竖屏极清海报 (9:16)", badge: "2K", badgeColor: "rose" };
  }
  if (w === 1280 && h === 720) {
    return { subLabel: "720P 高清横屏 (16:9)", badge: "720P", badgeColor: "zinc" };
  }
  if (w === 720 && h === 1280) {
    return { subLabel: "720P 高清竖屏 (9:16)", badge: "720P", badgeColor: "zinc" };
  }
  if (w === 1024 && h === 1024) {
    return { subLabel: "1K 标准正方形 (1:1)", badge: "1K", badgeColor: "emerald" };
  }
  if (w === 1536 && h === 1536) {
    return { subLabel: "1.5K 高清正方形 (1:1)", badge: "1.5K", badgeColor: "emerald" };
  }
  if (w === 2048 && h === 2048) {
    return { subLabel: "2K 超清正方形 (1:1)", badge: "2K", badgeColor: "blue" };
  }
  if (w === 1792 && h === 1024) {
    return { subLabel: "DALL-E 3 / Flux 推荐宽屏", badge: "DALL-E 3", badgeColor: "blue" };
  }
  if (w === 1024 && h === 1792) {
    return { subLabel: "DALL-E 3 / Flux 推荐长屏", badge: "DALL-E 3", badgeColor: "rose" };
  }
  if (w === 1344 && h === 768) {
    return { subLabel: "SDXL 官方推荐宽屏", badge: "SDXL", badgeColor: "blue" };
  }
  if (w === 768 && h === 1344) {
    return { subLabel: "SDXL 官方推荐长屏", badge: "SDXL", badgeColor: "rose" };
  }
  if (w === 2560 && h === 1080) {
    return { subLabel: "21:9 电影全景超宽", badge: "21:9", badgeColor: "blue" };
  }

  if (maxD >= 2000) {
    return { subLabel: "2K 级超清规格", badge: "2K", badgeColor: "blue" };
  }
  if (maxD >= 1400) {
    return { subLabel: "HD+ 高清规格", badge: "HD+", badgeColor: "emerald" };
  }
  if (maxD >= 1000) {
    return { subLabel: "1K 级标准分辨率", badge: "1K", badgeColor: "zinc" };
  }
  return { subLabel: "标准分辨率", badge: "标清", badgeColor: "zinc" };
}
