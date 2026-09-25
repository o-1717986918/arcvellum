<script setup lang="ts">
import { defineAsyncComponent } from "vue";
import SpatialWindowFrame from "@/features/orrery/SpatialWindowFrame.vue";
import type { SpatialWindow, SpatialWindowPosition, SpatialWindowSize } from "@/types/spatialWindows";

defineProps<{ item: SpatialWindow }>();
defineEmits<{
  move: [position: SpatialWindowPosition];
  resize: [size: SpatialWindowSize];
  close: [];
  toggle: [];
  reset: [];
  workspaceMode: [mode: "float" | "fullscreen"];
}>();

const SceneRehearsalView = defineAsyncComponent(() => import("@/features/creative-live/SceneRehearsalView.vue"));
</script>

<template>
  <SpatialWindowFrame
    class="pa-rehearsal-window"
    :item="item"
    @move="$emit('move', $event)"
    @resize="$emit('resize', $event)"
    @close="$emit('close')"
    @toggle="$emit('toggle')"
    @reset="$emit('reset')"
    @workspace-mode="$emit('workspaceMode', $event)"
  ><SceneRehearsalView /></SpatialWindowFrame>
</template>
