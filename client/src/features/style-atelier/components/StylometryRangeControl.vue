<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { MetricRow, MetricTarget } from "../stylometryTypes";
const props = defineProps<{ metric: MetricRow; target?: MetricTarget; disabled: boolean }>();
const emit = defineEmits<{ update: [target: MetricTarget] }>();
const domainMax = ref(1);
const step = computed(() => props.metric.ceiling === 1 ? 0.001 : 0.01);
function niceMax(number: number) {
  const power = 10 ** Math.floor(Math.log10(Math.max(1, number)));
  return [1, 2, 5, 10].map(multiplier => multiplier * power).find(value => value >= number) || number;
}
function resetDomain() {
  const row = props.metric;
  domainMax.value = row.ceiling === 1 ? 1 : Math.min(row.ceiling ?? Infinity,
    niceMax(Math.max(row.floor + 1, row.suggested.max * 1.5, props.target?.max || 0, row.observed || 0)));
}
watch(() => props.metric, resetDomain, { immediate: true });
watch(() => props.target?.max, max => {
  if (max != null && max > domainMax.value) domainMax.value = Math.min(props.metric.ceiling ?? Infinity, niceMax(max));
});
const position = (value: number) => Math.max(0, Math.min(100, (value - props.metric.floor) / (domainMax.value - props.metric.floor) * 100));
const band = computed(() => ({ left: `${position(props.target?.min ?? 0)}%`,
  width: `${position(props.target?.max ?? 0) - position(props.target?.min ?? 0)}%` }));
const show = (number: number | null) => number == null ? "缺测" : Number(number.toFixed(4)).toString();
function change(bound: "min" | "max", event: Event) {
  const raw = (event.target as HTMLInputElement).value;
  if (!props.target || !raw.trim() || !Number.isFinite(Number(raw))) return;
  let value = Math.max(props.metric.floor, Math.min(props.metric.ceiling ?? Infinity, Number(raw)));
  value = bound === "min" ? Math.min(value, props.target.max) : Math.max(value, props.target.min);
  emit("update", { ...props.target, [bound]: value });
}
function enable(event: Event) {
  emit("update", { ...(props.target || { id: props.metric.id, unit: props.metric.unit, ...props.metric.suggested }),
    enabled: (event.target as HTMLInputElement).checked });
}
</script>
<template>
  <article class="stylo-range-card" :data-enabled="Boolean(target?.enabled)" :data-metric="metric.id">
    <header><label><input type="checkbox" :checked="target?.enabled || false" :disabled="disabled || !metric.available" @change="enable" />{{ metric.label }}</label><span>语料 {{ show(metric.observed) }}</span></header>
    <template v-if="target">
      <div class="stylo-range-summary">
        <div class="stylo-range-base"></div><div class="stylo-range-band" :style="band"></div>
        <i v-if="metric.observed != null" class="stylo-range-observed" :style="{ left: position(metric.observed) + '%' }" :title="'语料实测 ' + show(metric.observed)"></i>
      </div>
      <label class="stylo-range-slider">下界<input type="range" :aria-label="metric.label + '下界滑块'" :min="metric.floor" :max="domainMax" :step="step" :value="target.min" :disabled="disabled || !metric.available" @input="change('min', $event)" /></label>
      <label class="stylo-range-slider">上界<input type="range" :aria-label="metric.label + '上界滑块'" :min="metric.floor" :max="domainMax" :step="step" :value="target.max" :disabled="disabled || !metric.available" @input="change('max', $event)" /></label>
      <div class="stylo-range-numbers"><label>下界<input type="number" :value="target.min" :min="metric.floor" :max="metric.ceiling ?? undefined" step="any" :disabled="disabled || !metric.available" :aria-label="metric.label + '目标下界'" @input="change('min', $event)" /></label><span>—</span><label>上界<input type="number" :value="target.max" :min="metric.floor" :max="metric.ceiling ?? undefined" step="any" :disabled="disabled || !metric.available" :aria-label="metric.label + '目标上界'" @input="change('max', $event)" /></label><small>{{ metric.unit }}</small></div>
      <footer><span>拖动范围 {{ metric.floor }}–{{ domainMax }}</span><button v-if="domainMax < (metric.ceiling ?? Infinity)" :disabled="disabled" @click="domainMax = Math.min(metric.ceiling ?? Infinity, domainMax * 2)">扩大拖动范围</button></footer>
    </template>
    <template v-else><p class="stylo-hint">未纳入此版本</p><button :disabled="disabled" @click="emit('update', { id: metric.id, unit: metric.unit, ...metric.suggested, enabled: false })">加入此指标</button></template>
  </article>
</template>
