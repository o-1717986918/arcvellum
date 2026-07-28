export interface CameraPose {
  x: number;
  y: number;
  scale: number;
}

export function cameraPoseAt(from: CameraPose, to: CameraPose, progress: number): CameraPose {
  const clamped = Math.max(0, Math.min(1, progress));
  const eased = 1 - Math.pow(1 - clamped, 4);
  return {
    x: lerp(from.x, to.x, eased),
    y: lerp(from.y, to.y, eased),
    scale: lerp(from.scale, to.scale, eased),
  };
}

export function cameraTransitionDuration(
  motion: "full" | "reduced" | "still",
  requestedDuration: number,
): number {
  if (motion === "still") return 0;
  return motion === "reduced" ? Math.min(200, requestedDuration) : requestedDuration;
}

function lerp(start: number, end: number, ratio: number): number {
  return start + (end - start) * ratio;
}
