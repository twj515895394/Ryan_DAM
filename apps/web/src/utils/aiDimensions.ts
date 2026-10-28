/**
 * AI 图像生成画幅比例与尺寸分辨率智能解析及匹配工具
 */

export const STANDARD_ASPECT_RATIOS = ["1:1", "16:9", "9:16", "4:3", "3:4"] as const;
export type StandardAspectRatio = typeof STANDARD_ASPECT_RATIOS[number];

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
  candidateRatios: string[] = ["1:1", "16:9", "9:16", "4:3", "3:4"]
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
    default:
      return "按特定比例渲染";
  }
}
