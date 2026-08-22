import type { WorldPoint } from "@/types/spatial";
import { parallaxViewFromDrag, type ParallaxView } from "./parallaxProjection";

export interface OrbitInteractionControls {
  currentView(): ParallaxView;
  pivot(): WorldPoint | null;
  cancelAnimation(): void;
  updateView(view: ParallaxView, pivot: WorldPoint | null): void;
}

export function attachOrbitInteraction(canvas: HTMLCanvasElement, controls: OrbitInteractionControls): () => void {
  let pointer: { pointerId: number; clientX: number; clientY: number; view: ParallaxView; pivot: WorldPoint | null } | null = null;
  const onPointerDown = (event: PointerEvent) => {
    // Left drag rotates empty sky while node clicks are handled by the DOM
    // overlay. Middle drag remains spatial translation; Alt-middle is an
    // equivalent orbit gesture for users who prefer a single navigation key.
    const leftOrbit = event.button === 0;
    const alternateOrbit = event.button === 1 && event.altKey;
    if (!leftOrbit && !alternateOrbit) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    controls.cancelAnimation();
    pointer = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      view: { ...controls.currentView() },
      pivot: controls.pivot(),
    };
    canvas.dataset.orbiting = "true";
    canvas.setPointerCapture?.(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent) => {
    if (!pointer || pointer.pointerId !== event.pointerId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    controls.updateView(
      parallaxViewFromDrag(pointer.view, event.clientX - pointer.clientX, event.clientY - pointer.clientY),
      pointer.pivot,
    );
  };
  const onPointerStop = (event: PointerEvent) => {
    if (!pointer || pointer.pointerId !== event.pointerId) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    pointer = null;
    delete canvas.dataset.orbiting;
    if (canvas.hasPointerCapture?.(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  };
  const onAuxClick = (event: MouseEvent) => {
    if (event.button === 1) event.preventDefault();
  };
  canvas.addEventListener("pointerdown", onPointerDown, true);
  canvas.addEventListener("pointermove", onPointerMove, true);
  canvas.addEventListener("pointerup", onPointerStop, true);
  canvas.addEventListener("pointercancel", onPointerStop, true);
  canvas.addEventListener("auxclick", onAuxClick, true);
  return () => {
    canvas.removeEventListener("pointerdown", onPointerDown, true);
    canvas.removeEventListener("pointermove", onPointerMove, true);
    canvas.removeEventListener("pointerup", onPointerStop, true);
    canvas.removeEventListener("pointercancel", onPointerStop, true);
    canvas.removeEventListener("auxclick", onAuxClick, true);
  };
}
