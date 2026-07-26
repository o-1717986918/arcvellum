<script setup lang="ts">
import { computed, ref } from "vue";
import { Eye, EyeOff, RotateCcw, ScanSearch, SlidersHorizontal } from "lucide-vue-next";
import type { RelationFamily, RelationVisibilityProfile } from "@/features/orrery/model/relations";

const props = defineProps<{
  profiles: RelationVisibilityProfile[];
  hidden: RelationFamily[];
  solo: RelationFamily | "";
}>();
const emit = defineEmits<{
  toggle: [family: RelationFamily];
  solo: [family: RelationFamily | ""];
  reset: [];
}>();

const expanded = ref(false);
const hiddenSet = computed(() => new Set(props.hidden));
const visibleCount = computed(() => props.solo ? 1 : props.profiles.filter((profile) => !hiddenSet.value.has(profile.family)).length);
</script>

<template>
  <aside class="relation-lens" :class="{ expanded }" aria-label="叙事关系镜头">
    <button class="relation-lens-trigger" :aria-expanded="expanded" title="筛选和聚焦叙事关系" @click="expanded = !expanded">
      <SlidersHorizontal :size="14" />
      <span><small>关系镜头</small><strong>{{ solo ? "独看 1 类" : `${visibleCount} 类可见` }}</strong></span>
    </button>
    <div v-if="expanded" class="relation-lens-panel">
      <header>
        <span><small>SEMANTIC LENS</small><strong>叙事关系</strong></span>
        <button title="恢复全部关系" aria-label="恢复全部关系" @click="emit('reset')"><RotateCcw :size="13" /></button>
      </header>
      <p>保留全书结构，只调整关系证据的显隐与强调。</p>
      <ol>
        <li v-for="profile in profiles" :key="profile.family" :class="{ muted: hiddenSet.has(profile.family), solo: solo === profile.family }">
          <button
            :title="hiddenSet.has(profile.family) ? `显示${profile.label}` : `隐藏${profile.label}`"
            :aria-pressed="!hiddenSet.has(profile.family)"
            @click="emit('toggle', profile.family)"
          >
            <EyeOff v-if="hiddenSet.has(profile.family)" :size="13" />
            <Eye v-else :size="13" />
            <span>{{ profile.label }}</span>
            <small>{{ profile.edge_count }}</small>
          </button>
          <button
            class="relation-lens-solo"
            :class="{ active: solo === profile.family }"
            :title="solo === profile.family ? '退出独看' : `只看${profile.label}`"
            :aria-pressed="solo === profile.family"
            @click="emit('solo', solo === profile.family ? '' : profile.family)"
          >
            <ScanSearch :size="12" />
          </button>
        </li>
      </ol>
    </div>
  </aside>
</template>
