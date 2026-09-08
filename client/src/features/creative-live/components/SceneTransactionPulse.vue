<script setup lang="ts">
import { computed } from "vue";
import { AlertCircle, BookOpenText, ShieldCheck } from "lucide-vue-next";
import type { SceneTransactionSummary } from "../types";

const props = defineProps<{ transaction?: SceneTransactionSummary | null }>();

const steps = [
  ["prepared", "资料"],
  ["creating", "创作"],
  ["verifying", "校验"],
  ["reviewing", "审读"],
  ["revision-needed", "修订"],
  ["committable", "待提交"],
  ["committed", "已入卷"],
] as const;

const currentIndex = computed(() => {
  const status = props.transaction?.status || "";
  if (status === "blocked") return -1;
  const value = steps.findIndex(([id]) => id === status);
  return value < 0 ? 0 : value;
});

function riskLabel(value: string): string {
  return { low: "轻量", standard: "标准", high: "关键" }[value] || "标准";
}
</script>

<template>
  <section v-if="transaction" class="scene-transaction-pulse" :data-status="transaction.status" :data-risk="transaction.risk">
    <div class="scene-transaction-copy">
      <span><BookOpenText :size="13" />{{ transaction.scene_id }}</span>
      <strong>{{ transaction.objective || '正在推进当前场景' }}</strong>
      <small>{{ riskLabel(transaction.risk) }}风险 · {{ transaction.body_hanzi.toLocaleString('zh-CN') }} 字</small>
    </div>
    <ol>
      <li v-for="([id, label], index) in steps" :key="id" :class="{ complete: currentIndex > index || transaction.status === 'committed', active: currentIndex === index }">
        <i></i><span>{{ label }}</span>
      </li>
    </ol>
    <div class="scene-transaction-result">
      <AlertCircle v-if="transaction.requires_input || transaction.status === 'blocked'" :size="14" />
      <ShieldCheck v-else :size="14" />
      <span>{{ transaction.requires_input ? '等待决定' : transaction.review_decision === 'revise' ? '正在定向修订' : transaction.warning_count ? `${transaction.warning_count} 条提示` : '链路正常' }}</span>
    </div>
  </section>
</template>
