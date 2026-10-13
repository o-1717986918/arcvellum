<script setup lang="ts">
import type { UsageAccounting } from "../types";
defineProps<{ accounting?: UsageAccounting; tokens: number; catalog: number }>();
</script>

<template>
  <details class="usage-evidence" aria-label="费用与调用记录">
    <summary>{{ Number(tokens).toLocaleString('zh-CN') }} Token · 费用记录</summary>
    <div class="usage-evidence-body">
      <p v-if="Number(accounting?.catalog_estimate_usd ?? catalog) > 0">目录估算 ${{ Number(accounting?.catalog_estimate_usd ?? catalog).toFixed(4) }}{{ accounting?.unknown_catalog_cost_updates || accounting?.unknown_usage_invocations ? '（已知部分）' : '' }}</p>
      <p v-else>目录费用暂无可核对记录</p>
      <p v-if="accounting?.public_estimate_cny != null">公开价格估算 ¥{{ accounting.public_estimate_cny.toFixed(4) }}{{ accounting.public_estimate_complete ? '' : '（已知部分）' }}</p>
      <p v-else>公开价格估算尚缺依据</p>
      <p>{{ accounting?.outer_invocations ?? '未知' }} 次角色调用 · {{ accounting?.recorded_model_turns ?? '未知' }} 个模型轮次 · {{ accounting?.observed_http_attempts ?? '未知' }} 次可观测 HTTP 尝试</p>
      <p>未知用量 {{ accounting?.unknown_usage_updates ?? '未知' }} 条 · 目录费用缺失 {{ accounting?.unknown_catalog_cost_updates ?? '未知' }} 条</p>
      <p v-if="accounting?.unknown_usage_invocations">另有 {{ accounting.unknown_usage_invocations }} 次调用尚未返回用量</p>
      <p v-if="accounting?.actual_charge">独立扣款记录：{{ accounting.actual_charge.currency }} {{ accounting.actual_charge.amount }}</p>
      <p v-else>实际扣款尚未核验</p>
      <p v-for="source in accounting?.price_sources || []" :key="source.source"><a :href="source.source" target="_blank" rel="noreferrer">价格依据</a> · 查询日期 {{ source.observed_at }} · {{ source.currency }}</p>
      <small>思考已包含在输出计费中。估算按已记录用量去重，实际扣款单独核对。</small>
    </div>
  </details>
</template>

<style scoped>
.usage-evidence { position: relative; min-width: 0; text-align: right; }
.usage-evidence summary { cursor: pointer; }
.usage-evidence-body { position: absolute; right: 0; bottom: 28px; z-index: 40; width: min(440px, calc(100vw - 48px)); max-height: 50vh; overflow: auto; padding: 14px; border: 1px solid #bdd7c7; border-radius: 7px; background: #f8faf7; color: #263831; text-align: left; box-shadow: 0 8px 28px #26383122; }
.usage-evidence-body p { margin: 0 0 8px; white-space: normal; overflow-wrap: anywhere; line-height: 1.65; }
.usage-evidence-body small { white-space: normal; line-height: 1.6; }
.usage-evidence summary:focus-visible { outline: 2px solid #2f705d; outline-offset: 3px; }
</style>
