<script setup lang="ts">
import { computed } from "vue";
import { Link2, UserRound } from "lucide-vue-next";
import type { SpatialNarrativeEdge, SpatialNarrativeNode } from "@/types/spatial";

const props = defineProps<{
  nodes: SpatialNarrativeNode[];
  edges: SpatialNarrativeEdge[];
  activeCharacterId?: string;
}>();
const emit = defineEmits<{ select: [nodeId: string] }>();

const threads = computed(() => {
  const chapters = new Set(props.nodes.filter((node) => node.type === "chapter").map((node) => node.node_id));
  const characters = new Map(props.nodes.filter((node) => node.type === "character").map((node) => [node.node_id, node]));
  const participation = new Map<string, Set<string>>();
  for (const edge of props.edges) {
    if (edge.type !== "participates") continue;
    const characterId = chapters.has(edge.source) ? edge.target : chapters.has(edge.target) ? edge.source : "";
    const chapterId = chapters.has(edge.source) ? edge.source : chapters.has(edge.target) ? edge.target : "";
    if (!characterId || !chapterId || !characters.has(characterId)) continue;
    const linked = participation.get(characterId) || new Set<string>();
    linked.add(chapterId);
    participation.set(characterId, linked);
  }
  return [...participation.entries()]
    .map(([nodeId, chapterIds]) => ({ node: characters.get(nodeId)!, count: chapterIds.size }))
    .sort((left, right) => right.count - left.count || left.node.label.localeCompare(right.node.label));
});
</script>

<template>
  <aside v-if="threads.length" class="character-thread-rail" aria-label="人物章节关系">
    <div><Link2 :size="12" /><span>人物线索</span></div>
    <button
      v-for="thread in threads.slice(0, 7)"
      :key="thread.node.node_id"
      :class="{ active: activeCharacterId === thread.node.node_id }"
      :title="`${thread.node.label} 进入 ${thread.count} 个章节`"
      :aria-pressed="activeCharacterId === thread.node.node_id"
      @click="emit('select', activeCharacterId === thread.node.node_id ? '' : thread.node.node_id)"
    >
      <UserRound :size="13" /><span>{{ thread.node.label }}</span><small>{{ thread.count }} 章</small>
    </button>
  </aside>
</template>
