<script setup lang="ts">
import { computed } from "vue";
import { CircleAlert, Link2, UserRound } from "lucide-vue-next";
import {
  buildCharacterThreadGroups,
  type CharacterReference,
} from "@/features/orrery/model/characters";
import type { SpatialNarrativeNode } from "@/types/spatial";

const props = defineProps<{
  nodes: SpatialNarrativeNode[];
  references: CharacterReference[];
  activeCharacterId?: string;
  activeChapterId?: string;
}>();
const emit = defineEmits<{ select: [nodeId: string] }>();

const groups = computed(() => buildCharacterThreadGroups(
  props.references,
  props.nodes,
  String(props.activeChapterId || "").replace(/^chapter:/, ""),
));
</script>

<template>
  <aside v-if="groups.length" class="character-thread-rail" aria-label="人物章节关系">
    <div><Link2 :size="12" /><span>人物线索</span></div>
    <section v-for="group in groups" :key="group.id" :data-group="group.id">
      <small>{{ group.label }}</small>
      <button
        v-for="thread in group.items"
        :key="thread.node.node_id"
        :class="{ active: activeCharacterId === thread.node.node_id, unresolved: group.id === 'unresolved' }"
        :title="thread.reference.resolution === 'resolved'
          ? `${thread.node.label} 进入 ${thread.chapterCount} 个章节、${thread.sceneCount} 个场景`
          : `${thread.node.label} 尚未唯一解析为正式人物`"
        :aria-pressed="activeCharacterId === thread.node.node_id"
        @click="emit('select', activeCharacterId === thread.node.node_id ? '' : thread.node.node_id)"
      >
        <CircleAlert v-if="group.id === 'unresolved'" :size="13" />
        <UserRound v-else :size="13" />
        <span>{{ thread.node.label }}</span>
        <small>{{ thread.reference.resolution === "resolved" ? `${thread.chapterCount} 章` : "待确认" }}</small>
      </button>
    </section>
  </aside>
</template>
