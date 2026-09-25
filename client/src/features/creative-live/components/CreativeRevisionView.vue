<script setup lang="ts">
import { computed, ref } from "vue";
import { GitCompareArrows, ScrollText } from "lucide-vue-next";
import SafeMarkdown from "@/components/SafeMarkdown.vue";
import type { ArtifactRevision, ArtifactRevisionSummary, CreativeArtifact } from "../types";
import { artifactTitle } from "../artifactPresentation";
import RevisionDiff from "./RevisionDiff.vue";

const props = defineProps<{
  artifact?: CreativeArtifact | null;
  revisions: ArtifactRevisionSummary[];
  selectedRevision?: ArtifactRevision | null;
  comparisonRevision?: ArtifactRevision | null;
}>();
const emit = defineEmits<{ selectRevision: [revisionId: string] }>();
const comparison = ref(true);
const ordered = computed(() => props.revisions);
const content = computed(() => props.selectedRevision?.content || props.artifact?.content || "");
const displayedChange = computed(() => props.selectedRevision?.diff ? props.selectedRevision : props.comparisonRevision);

function revisionLabel(item: ArtifactRevisionSummary, index: number): string {
  if (item.identity === "promoted") return "正式晋升";
  return index === 0 ? "初稿" : `修订 ${index}`;
}
</script>

<template>
  <section class="live-manuscript creative-revision-workspace" aria-label="正文修订">
    <header>
      <div>
        <span class="creative-live-kicker">正文修订</span>
        <h2>{{ artifactTitle(artifact) }}</h2>
        <p>{{ selectedRevision ? `${selectedRevision.characters.toLocaleString('zh-CN')} 字符 · ${selectedRevision.identity === 'promoted' ? '正式版本' : '候选版本'}` : '选择版本阅读全文与变化' }}</p>
      </div>
      <div class="live-manuscript-controls">
        <button :class="{ active: !comparison }" @click="comparison = false"><ScrollText :size="13" />全文</button>
        <button :class="{ active: comparison }" @click="comparison = true"><GitCompareArrows :size="13" />比较变化</button>
      </div>
    </header>
    <nav v-if="ordered.length" class="creative-revision-workspace-selector" aria-label="正文版本">
      <button v-for="(revision, index) in ordered" :key="revision.revision_id"
        :class="{ active: selectedRevision?.revision_id === revision.revision_id }"
        @click="emit('selectRevision', revision.revision_id)">
        <span>{{ revisionLabel(revision, index) }}</span><small>{{ revision.characters.toLocaleString('zh-CN') }} 字符</small>
      </button>
    </nav>
    <div class="creative-revision-workspace-scroll">
      <RevisionDiff v-if="comparison && selectedRevision" :revision="displayedChange" :inherited="!!comparisonRevision && displayedChange?.revision_id === comparisonRevision.revision_id" />
      <div v-else-if="content" class="live-manuscript-scroll"><SafeMarkdown :source="content" variant="document" /></div>
      <div v-else class="creative-live-empty manuscript-empty"><ScrollText :size="26" /><strong>还没有可对照的正文版本</strong><p>主创落笔并修订后，可在这里阅读完整版本和每次变化。</p></div>
    </div>
  </section>
</template>
