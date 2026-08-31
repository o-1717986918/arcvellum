<script setup lang="ts">
import { CheckCircle2, ScanSearch, ShieldAlert } from "lucide-vue-next";
import type { CreativeReview } from "../types";

defineProps<{ reviews?: CreativeReview[] }>();

function timeLabel(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
</script>

<template>
  <section class="creative-review-rail">
    <header><span>审查轨迹</span><strong>{{ reviews?.length || 0 }} 条证据</strong></header>
    <ol v-if="reviews?.length">
      <li v-for="item in reviews.slice(-10).reverse()" :key="item.event_id" :data-status="item.status || item.event">
        <span class="review-mark"><CheckCircle2 v-if="/pass|complete|approved/.test(item.status || item.event)" :size="13" /><ShieldAlert v-else-if="/fail|reject|block/.test(item.status || item.event)" :size="13" /><ScanSearch v-else :size="13" /></span>
        <div><strong>{{ item.title || '审查状态更新' }}</strong><p>{{ item.message || '本轮审查已有新结论。' }}</p><small>{{ timeLabel(item.at) }}</small></div>
      </li>
    </ol>
    <div v-else class="creative-live-empty compact"><ScanSearch :size="21" /><p>候选稿形成后，机器检查与语义审读会依次出现。</p></div>
  </section>
</template>

