export interface CreativeProgressionPosition {
  x: number;
  y: number;
}

export function creativeProgressionPositions(
  count: number,
  width: number,
  anchorCenterX: number,
  anchorCenterY: number,
): CreativeProgressionPosition[] {
  if (count <= 0) return [];
  const stageWidth = Math.max(280, width);
  if (stageWidth <= 680) return compactPositions(count, stageWidth);

  const leftSafeArea = 84;
  const rightSafeArea = stageWidth <= 1120 ? 172 : 126;
  const cardRadius = 66;
  const usableLeft = leftSafeArea + cardRadius;
  const usableRight = stageWidth - rightSafeArea - cardRadius;
  const availableSpan = Math.max(0, usableRight - usableLeft);
  const spread = count > 1 ? Math.min(154, availableSpan / (count - 1)) : 0;
  const halfSpan = spread * (count - 1) / 2;
  const minCenter = usableLeft + halfSpan;
  const maxCenter = usableRight - halfSpan;
  const fallbackCenter = (usableLeft + usableRight) / 2;
  const centerX = minCenter <= maxCenter
    ? clamp(anchorCenterX || fallbackCenter, minCenter, maxCenter)
    : fallbackCenter;
  const routeY = clamp(anchorCenterY - 190, 82, 148);
  const stagger = spread < 136 ? 23 : 14;
  const middle = (count - 1) / 2;

  return Array.from({ length: count }, (_, index) => {
    const offset = index - middle;
    return {
      x: centerX + offset * spread,
      y: routeY + (index % 2 === 0 ? -stagger : stagger),
    };
  });
}

function compactPositions(count: number, width: number): CreativeProgressionPosition[] {
  const columns = count === 1 ? 1 : 2;
  const left = columns === 1 ? width / 2 : 72;
  const right = width - 72;
  return Array.from({ length: count }, (_, index) => ({
    x: columns === 1 ? left : (index % columns === 0 ? left : right),
    y: 48 + Math.floor(index / columns) * 52,
  }));
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
