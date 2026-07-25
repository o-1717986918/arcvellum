<script setup lang="ts">
import { Circle, X } from "lucide-vue-next";

defineProps<{
  tabs: Array<{ id: string; title: string; kind: "asset" | "candidate" }>;
  activeId?: string;
  dirtyIds?: string[];
}>();
const emit = defineEmits<{
  select: [id: string, kind: "asset" | "candidate"];
  close: [id: string, kind: "asset" | "candidate"];
}>();
</script>

<template>
  <nav class="archive-tabs" aria-label="已打开资料">
    <div
      v-for="tab in tabs"
      :key="`${tab.kind}:${tab.id}`"
      :class="{ active: activeId === tab.id }"
    >
      <button
        class="archive-tab-select"
        @click="emit('select', tab.id, tab.kind)"
      >
        <Circle v-if="tab.kind === 'asset' && dirtyIds?.includes(tab.id)" :size="7" fill="currentColor" />
        <span>{{ tab.title }}</span>
        <small>{{ tab.kind === "candidate" ? "候选" : "正式" }}</small>
      </button>
      <button
        class="archive-tab-close"
        type="button"
        title="关闭标签"
        :aria-label="`关闭 ${tab.title}`"
        @click="emit('close', tab.id, tab.kind)"
      ><X :size="12" /></button>
    </div>
  </nav>
</template>
