export interface CameraFrame {
  x: number;
  y: number;
  scale: number;
}

export interface CameraAnimation {
  from: CameraFrame;
  to: CameraFrame;
  elapsed: number;
  duration: number;
}

export interface CameraAnimationStep {
  frame: CameraFrame;
  animation: CameraAnimation | null;
}

export function advanceCameraAnimation(animation: CameraAnimation, deltaMs: number): CameraAnimationStep {
  const elapsed = Math.min(animation.duration, animation.elapsed + deltaMs);
  const progress = elapsed / animation.duration;
  const eased = 1 - Math.pow(1 - progress, 4);
  const frame = {
    x: interpolate(animation.from.x, animation.to.x, eased),
    y: interpolate(animation.from.y, animation.to.y, eased),
    scale: interpolate(animation.from.scale, animation.to.scale, eased),
  };
  return {
    frame,
    animation: progress >= 1 ? null : { ...animation, elapsed },
  };
}

function interpolate(start: number, end: number, ratio: number): number {
  return start + (end - start) * ratio;
}
