<script setup lang="ts">
import { Clock3, GitCommitHorizontal } from "lucide-vue-next";

defineProps<{ history: Record<string, unknown> }>();

function rows(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
}

function short(value: unknown): string {
  const text = String(value || "");
  return text.length > 18 ? `${text.slice(0, 18)}…` : text;
}
</script>

<template>
  <section class="archive-timeline">
    <header><Clock3 :size="15" /><strong>版本时间线</strong></header>
    <ol v-if="rows(history.revisions).length">
      <li v-for="revision in rows(history.revisions).slice(0, 12)" :key="String(revision.revision)">
        <i><GitCommitHorizontal :size="12" /></i>
        <div><strong>{{ short(revision.revision) }}</strong><p>{{ revision.created_at || revision.recorded_at || "项目历史版本" }}</p></div>
      </li>
    </ol>
    <p v-else class="archive-panel-empty">这份资料还没有作者修订记录。</p>
  </section>
</template>
