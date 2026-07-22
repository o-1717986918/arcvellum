<script setup lang="ts">
import type { SpatialNarrativeNode } from "@/types/spatial";

defineProps<{ nodes: SpatialNarrativeNode[]; selectedNodeId?: string }>();
const emit = defineEmits<{ select: [node: SpatialNarrativeNode] }>();
</script>

<template>
  <section class="orrery-v3-accessible" aria-label="叙事场域列表">
    <button v-for="node in nodes" :key="node.node_id" :class="{ selected: selectedNodeId === node.node_id }" :data-status="node.status" @click="emit('select', node)">
      <i></i><span><strong>{{ node.label }}</strong><small>{{ node.subtitle || node.type }}</small></span><em>{{ node.status }}</em>
    </button>
  </section>
</template>
