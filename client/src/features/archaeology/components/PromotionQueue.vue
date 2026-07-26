<script setup lang="ts">
import { Archive, ArrowRight, CircleCheck, Clock3 } from "lucide-vue-next";
import type { ArchaeologyPromotionQueue } from "../types";

defineProps<{ queue: ArchaeologyPromotionQueue; analysisOnly: boolean }>();
</script>

<template>
  <section class="archaeology-promotion-queue">
    <header>
      <span><Archive :size="15" />候选入档</span>
      <small>{{ analysisOnly ? "分析模式不写入资产" : `${queue.ready_count} 份待审` }}</small>
    </header>
    <div v-if="analysisOnly" class="archaeology-analysis-boundary">
      <CircleCheck :size="18" />
      <strong>只保留分析结论</strong>
      <p>这次整理不会创建可晋升的人物、世界观或情节资产。</p>
    </div>
    <ol v-else-if="queue.items.length">
      <li v-for="item in queue.items" :key="item.candidate_id">
        <Clock3 :size="13" />
        <span><strong>{{ item.candidate_id }}</strong><small>{{ item.asset_type }}</small></span>
      </li>
    </ol>
    <div v-else class="archaeology-panel-empty compact">
      通过领域审查的候选会先进入档案管理，再由正式 Gate 决定是否晋升。
    </div>
    <RouterLink v-if="!analysisOnly && queue.ready_count" class="archaeology-archive-link" to="/archive">
      前往档案管理<ArrowRight :size="13" />
    </RouterLink>
  </section>
</template>
