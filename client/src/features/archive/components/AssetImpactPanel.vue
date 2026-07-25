<script setup lang="ts">
import { CheckCircle2, CircleAlert, GitCompareArrows, ShieldCheck } from "lucide-vue-next";

defineProps<{
  validation: Record<string, unknown> | null;
  impact: Record<string, unknown> | null;
}>();

function items(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}
</script>

<template>
  <section class="archive-impact">
    <header><GitCompareArrows :size="15" /><strong>变更影响</strong></header>
    <div v-if="!validation && !impact" class="archive-panel-empty">
      修改内容后运行“检查变更”，这里会显示结构、引用和下游失效范围。
    </div>
    <template v-else>
      <div class="archive-signal" :class="{ ready: validation?.valid === true }">
        <CheckCircle2 v-if="validation?.valid === true" :size="15" />
        <CircleAlert v-else :size="15" />
        <span><strong>{{ validation?.valid === true ? "结构检查通过" : "需要修正" }}</strong><small>{{ items(validation?.issues).length }} 项提示</small></span>
      </div>
      <ul v-if="items(validation?.issues).length" class="archive-issue-list">
        <li v-for="issue in items(validation?.issues)" :key="String(issue.code)">{{ issue.message || issue.code }}</li>
      </ul>
      <div v-if="impact" class="archive-impact-summary">
        <ShieldCheck :size="15" />
        <div>
          <strong>预计影响 {{ Number((impact.summary as Record<string, unknown>)?.reference_count || impact.reference_count || 0) }} 处引用</strong>
          <p v-if="strings(impact.stale_categories).length">将重新检查：{{ strings(impact.stale_categories).join("、") }}</p>
          <p v-else>未发现已经读取这份资料的正式上下文。</p>
        </div>
      </div>
    </template>
  </section>
</template>
