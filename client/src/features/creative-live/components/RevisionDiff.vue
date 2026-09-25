<script setup lang="ts">
import { computed } from "vue";
import { GitCompareArrows } from "lucide-vue-next";
import type { ArtifactRevision } from "../types";

const props = defineProps<{ revision?: ArtifactRevision | null; inherited?: boolean }>();
const lines = computed(() => String(props.revision?.diff || "").split("\n").filter((line) => !line.startsWith("@@") && !line.startsWith("---") && !line.startsWith("+++")));
</script>

<template>
  <section class="creative-revision-diff">
    <header><GitCompareArrows :size="14" /><strong>{{ inherited ? '正式稿承接的修订痕迹' : '本轮修订变化' }}</strong><span v-if="revision">{{ revision.characters.toLocaleString('zh-CN') }} 字符</span></header>
    <p v-if="inherited" class="creative-revision-inherited-note">正式晋升沿用了主创修订稿，未再次改字。下方标色显示该修订稿相对前一版的变化。</p>
    <div v-if="revision?.diff" class="revision-diff-scroll">
      <p v-for="(line, index) in lines" :key="index" :class="{ added: line.startsWith('+'), removed: line.startsWith('-'), context: !/^[+-]/.test(line) }">{{ line.slice(/^[+-]/.test(line) ? 1 : 0) || ' ' }}</p>
    </div>
    <div v-else class="creative-live-empty compact"><p>这一步没有文字变化；可切换其他版本或查看全文。</p></div>
  </section>
</template>
