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

function timestamp(revision: Record<string, unknown>): string {
  return String(revision.created_at || revision.recorded_at || "");
}

function readableTime(value: string): string {
  const date = new Date(value);
  if (!value) return "项目历史版本";
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(date);
}
</script>

<template>
  <section class="archive-timeline">
    <header><Clock3 :size="15" /><strong>版本时间线</strong></header>
    <ol v-if="rows(history.revisions).length">
      <li v-for="revision in rows(history.revisions).slice(0, 12)" :key="String(revision.revision)">
        <i><GitCommitHorizontal :size="12" /></i>
        <div>
          <strong :title="String(revision.revision || '')">{{ short(revision.revision) }}</strong>
          <time :datetime="timestamp(revision) || undefined" :title="timestamp(revision)">{{ readableTime(timestamp(revision)) }}</time>
        </div>
      </li>
    </ol>
    <p v-else class="archive-panel-empty">这份资料还没有作者修订记录。</p>
  </section>
</template>
