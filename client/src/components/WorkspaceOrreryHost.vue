<script setup lang="ts">
import { defineAsyncComponent } from "vue";

defineProps<{ dashboard: Record<string, unknown> | null; immersive?: boolean }>();
defineEmits<{ advance: []; inspectTask: []; openReader: []; choose: [choice: Record<string, unknown>] }>();

const OrreryWorkbench = defineAsyncComponent(() => import("@/features/orrery/OrreryWorkbench.vue"));
</script>

<template>
  <OrreryWorkbench
    :dashboard="dashboard"
    :immersive="immersive"
    @advance="$emit('advance')"
    @inspect-task="$emit('inspectTask')"
    @open-reader="$emit('openReader')"
    @choose="$emit('choose', $event)"
  />
</template>
