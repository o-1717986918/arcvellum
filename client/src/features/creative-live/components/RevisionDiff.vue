<script setup lang="ts">
import { computed } from "vue";
import { GitCompareArrows } from "lucide-vue-next";
import type { ArtifactRevision } from "../types";

const props = defineProps<{ revision?: ArtifactRevision | null }>();
const lines = computed(() => String(props.revision?.diff || "").split("\n").filter((line) => !line.startsWith("@@") && !line.startsWith("---") && !line.startsWith("+++")));
</script>

<template>
  <section class="creative-revision-diff">
    <header><GitCompareArrows :size="14" /><strong>本轮修订变化</strong><span v-if="revision">{{ revision.characters.toLocaleString('zh-CN') }} 字符</span></header>
    <div v-if="revision?.diff" class="revision-diff-scroll">
      <p v-for="(line, index) in lines" :key="index" :class="{ added: line.startsWith('+'), removed: line.startsWith('-'), context: !/^[+-]/.test(line) }">{{ line.slice(/^[+-]/.test(line) ? 1 : 0) || ' ' }}</p>
    </div>
    <div v-else class="creative-live-empty compact"><p>选择一个修订快照即可比较文本变化。</p></div>
  </section>
</template>

