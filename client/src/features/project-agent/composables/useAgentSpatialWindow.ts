import { ref, type Ref } from "vue";
import type { SpatialWindow, SpatialWindowPosition, SpatialWindowSize } from "@/types/spatialWindows";

/** Geometry and presentation for an Agent workspace's auxiliary window. */
export function useAgentSpatialWindow(root: Readonly<Ref<string>>, defaults: {
  id: string; title: string; width: number; height: number; layer: number;
}) {
  const item = ref<SpatialWindow | null>(null);
  function open(): boolean {
    if (!root.value) return false;
    if (item.value) { item.value.collapsed = false; return true; }
    const size = {
      width: Math.min(defaults.width, Math.max(320, window.innerWidth - 36)),
      height: Math.min(defaults.height, Math.max(420, window.innerHeight - 36)),
    };
    item.value = {
      id: defaults.id, kind: "observatory", title: defaults.title,
      position: { left: Math.max(12, Math.round((window.innerWidth - size.width) / 2)), top: Math.max(12, Math.round((window.innerHeight - size.height) / 2)) },
      size, layer: defaults.layer, collapsed: false, workspace_mode: window.innerWidth <= 760 ? "fullscreen" : "float",
    };
    return true;
  }
  function resize(size: SpatialWindowSize): void {
    if (!item.value) return;
    item.value.size = { width: Math.max(320, Math.min(size.width, window.innerWidth - 24)),
      height: Math.max(420, Math.min(size.height, window.innerHeight - 24)) };
  }
  function move(position: SpatialWindowPosition): void { if (item.value) item.value.position = position; }
  function setMode(mode: "float" | "fullscreen"): void {
    const current = item.value;
    if (!current) return;
    if (mode === "fullscreen") current.workspace_return = { position: { ...current.position }, size: { ...current.size } };
    else if (current.workspace_return) {
      current.position = current.workspace_return.position;
      current.size = current.workspace_return.size;
      current.workspace_return = undefined;
    }
    current.workspace_mode = mode;
  }
  return { item, open, resize, move, setMode };
}
