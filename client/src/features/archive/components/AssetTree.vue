<script setup lang="ts">
import { computed } from "vue";
import {
  ArchiveRestore,
  ChevronRight,
  FileClock,
  FileText,
  Search,
  Sparkles,
  UserRound,
} from "lucide-vue-next";
import { archiveAssetLabel } from "../registry/assetViews";
import type { ArchiveAssetGroup, ArchiveCandidate, RecycleEntry } from "../types";

const props = defineProps<{
  groups: ArchiveAssetGroup[];
  candidates: ArchiveCandidate[];
  recycleEntries: RecycleEntry[];
  mode: "formal" | "candidate" | "recycle";
  query: string;
  selectedId?: string;
}>();
const emit = defineEmits<{
  selectAsset: [id: string];
  selectCandidate: [id: string];
  updateQuery: [value: string];
}>();

const needle = computed(() => props.query.trim().toLocaleLowerCase());
const filteredGroups = computed(() =>
  props.groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => match(item.title, item.asset_id)),
    }))
    .filter((group) => group.items.length),
);
const filteredCandidates = computed(() =>
  props.candidates.filter((item) => match(item.title, item.candidate_id, item.asset_type)),
);
const filteredRecycle = computed(() =>
  props.recycleEntries.filter((item) => match(item.title, item.asset_id, item.reason)),
);

function match(...values: unknown[]): boolean {
  return !needle.value || values.join(" ").toLocaleLowerCase().includes(needle.value);
}
</script>

<template>
  <aside class="archive-tree" aria-label="作品资产">
    <label class="archive-tree-search">
      <Search :size="14" />
      <input
        :value="query"
        placeholder="筛选当前列表"
        @input="emit('updateQuery', ($event.target as HTMLInputElement).value)"
      />
    </label>

    <div v-if="mode === 'formal'" class="archive-tree-scroll">
      <section v-for="group in filteredGroups" :key="group.asset_type">
        <header>
          <span>{{ archiveAssetLabel(group.asset_type) }}</span>
          <small>{{ group.items.length }}</small>
        </header>
        <button
          v-for="item in group.items"
          :key="item.asset_id"
          :class="{ active: selectedId === item.asset_id }"
          @click="emit('selectAsset', item.asset_id)"
        >
          <UserRound v-if="item.asset_type === 'character'" :size="14" />
          <FileText v-else :size="14" />
          <span><strong>{{ item.title || item.asset_id }}</strong><small>{{ item.asset_id }}</small></span>
          <ChevronRight :size="13" />
        </button>
      </section>
      <p v-if="!filteredGroups.length" class="archive-tree-empty">没有匹配的正式资料。</p>
    </div>

    <div v-else-if="mode === 'candidate'" class="archive-tree-scroll">
      <button
        v-for="item in filteredCandidates"
        :key="item.candidate_id"
        :class="{ active: selectedId === item.candidate_id }"
        @click="emit('selectCandidate', item.candidate_id)"
      >
        <Sparkles :size="14" />
        <span><strong>{{ item.title || item.candidate_id }}</strong><small>{{ archiveAssetLabel(item.asset_type) }} · {{ item.current_step }}</small></span>
        <ChevronRight :size="13" />
      </button>
      <p v-if="!filteredCandidates.length" class="archive-tree-empty">当前没有候选资料。</p>
    </div>

    <div v-else class="archive-tree-scroll">
      <div v-for="item in filteredRecycle" :key="item.entry_id" class="archive-tree-recycle">
        <ArchiveRestore :size="14" />
        <span><strong>{{ item.title || item.asset_id }}</strong><small>{{ item.asset_id }}</small></span>
      </div>
      <p v-if="!filteredRecycle.length" class="archive-tree-empty">项目回收站是空的。</p>
    </div>

    <footer><FileClock :size="13" />项目文件仍是正式内容源</footer>
  </aside>
</template>
