<script setup lang="ts">
import { Activity } from "lucide-vue-next";
import type { CreativeActivity } from "../types";

defineProps<{ items?: CreativeActivity[] }>();

function eventTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "刚刚" : date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
</script>

<template>
  <section class="creative-execution-timeline">
    <header><Activity :size="13" /><strong>推进轨迹</strong></header>
    <ol v-if="items?.length">
      <li v-for="item in items.slice(-6).reverse()" :key="item.event_id">
        <i></i><div><strong>{{ item.title || '创作状态更新' }}</strong><small>{{ item.message || '作品继续推进。' }}</small></div><time>{{ eventTime(item.at) }}</time>
      </li>
    </ol>
    <p v-else>领取创作任务后，这里会出现真实的推进记录。</p>
  </section>
</template>
