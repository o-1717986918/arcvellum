<script setup lang="ts">
import { computed } from "vue";
import { BookMarked, ChevronRight } from "lucide-vue-next";
import type { SpatialNarrativeNode } from "@/types/spatial";

const props = defineProps<{ chapters: SpatialNarrativeNode[]; selectedNodeId?: string }>();
const emit = defineEmits<{ select: [nodeId: string] }>();

const ordered = computed(() => [...props.chapters].sort((left, right) => left.order - right.order));

function progress(node: SpatialNarrativeNode): number {
  const target = Number(node.metrics.word_target || 0);
  const actual = Number(node.metrics.formal_chars || 0);
  return target ? Math.min(100, Math.round(actual / target * 100)) : 0;
}
</script>

<template>
  <nav v-if="ordered.length" class="chapter-rail" aria-label="章节目录">
    <div class="chapter-rail-heading"><BookMarked :size="13" /><span>章节目录</span></div>
    <div class="chapter-rail-scroll" role="tablist" aria-label="已建立章节">
      <button
        v-for="(chapter, index) in ordered"
        :key="chapter.node_id"
        :class="{ active: selectedNodeId === chapter.node_id }"
        :data-status="chapter.status"
        role="tab"
        :aria-selected="selectedNodeId === chapter.node_id"
        @click="emit('select', chapter.node_id)"
      >
        <b>{{ String(index + 1).padStart(2, "0") }}</b>
        <span><strong>{{ chapter.label }}</strong><small>{{ Number(chapter.metrics.formal_chars || 0).toLocaleString() }} / {{ Number(chapter.metrics.word_target || 0).toLocaleString() }} 字</small></span>
        <i><em :style="{ width: `${progress(chapter)}%` }"></em></i>
        <ChevronRight :size="12" />
      </button>
    </div>
  </nav>
</template>
