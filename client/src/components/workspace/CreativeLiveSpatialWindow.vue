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

const CreativeLiveView = defineAsyncComponent(() => import("@/features/creative-live/CreativeLiveView.vue"));
</script>

<template>
  <SpatialWindowFrame
    class="pa-live-window"
    :item="item"
    @move="$emit('move', $event)"
    @resize="$emit('resize', $event)"
    @close="$emit('close')"
    @toggle="$emit('toggle')"
    @reset="$emit('reset')"
    @workspace-mode="$emit('workspaceMode', $event)"
  ><CreativeLiveView /></SpatialWindowFrame>
</template>
