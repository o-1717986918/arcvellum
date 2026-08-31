import { computed, watch, type ComputedRef } from "vue";
import { useCreativeLiveStore } from "@/features/creative-live/stores/creativeLive";
import type { SpatialNarrativeNode } from "@/types/spatial";
import { preferredLiveFocus } from "./liveCameraHints";
import { resolveLiveNodeIds } from "./liveNodeState";
import { liveWindowLabel } from "./liveWindowBinding";

interface OrreryCreativeLiveOptions {
  projectRoot: () => string;
  nodes: () => SpatialNarrativeNode[];
  openWorkspace: () => void;
  navigate: (node: SpatialNarrativeNode) => void;
}

interface OrreryCreativeLiveBinding {
  creativeLive: ReturnType<typeof useCreativeLiveStore>;
  liveNodeIds: ComputedRef<string[]>;
  creativeLiveLabel: ComputedRef<string>;
  openCreativeLive: () => void;
}

export function useOrreryCreativeLive(options: OrreryCreativeLiveOptions): OrreryCreativeLiveBinding {
  const creativeLive = useCreativeLiveStore();
  const liveNodeIds = computed(() => [...resolveLiveNodeIds(creativeLive.snapshot, options.nodes())]);
  const liveFocusNodeId = computed(() => preferredLiveFocus(options.nodes(), new Set(liveNodeIds.value)));
  const creativeLiveLabel = computed(() => liveWindowLabel(creativeLive.snapshot));

  watch(options.projectRoot, (root) => {
    if (root) void creativeLive.connect(root);
  }, { immediate: true });

  function openCreativeLive(): void {
    options.openWorkspace();
    const node = options.nodes().find((item) => item.node_id === liveFocusNodeId.value);
    if (node) options.navigate(node);
  }

  return { creativeLive, liveNodeIds, creativeLiveLabel, openCreativeLive };
}
