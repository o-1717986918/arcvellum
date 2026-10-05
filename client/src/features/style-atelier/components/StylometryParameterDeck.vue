<script setup lang="ts">
import { computed } from "vue";
import type { CreatorControls, MetricRow, MetricTarget } from "../stylometryTypes";
import StylometryRangeControl from "./StylometryRangeControl.vue";
const props = defineProps<{ metrics: MetricRow[]; modelValue: CreatorControls; disabled: boolean }>();
const emit = defineEmits<{ 'update:modelValue': [controls: CreatorControls] }>();
const groups = computed(() => [
  { id: "primary", label: "句段与声音 · 四主轴" }, { id: "secondary", label: "节奏、词汇与语法 · 九项目标" },
  { id: "lexical", label: "高频语法词" }, { id: "dependency", label: "依存句法 · 七项目标" },
].map(group => ({ ...group, rows: props.metrics.filter(metric => metric.group === group.id) })));
function update(target: MetricTarget) {
  const targets = props.modelValue.targets.some(row => row.id === target.id)
    ? props.modelValue.targets.map(row => row.id === target.id ? target : row) : [...props.modelValue.targets, target];
  emit('update:modelValue', { ...props.modelValue, targets });
}
</script>
<template>
  <div class="stylo-parameter-deck"><template v-for="group in groups" :key="group.id"><details v-if="group.rows.length" :open="group.id === 'primary'" :aria-label="group.label">
    <summary>{{ group.label }} <small>{{ group.rows.length }} 项</small></summary><div class="stylo-range-grid"><StylometryRangeControl v-for="row in group.rows" :key="row.id" :metric="row" :target="modelValue.targets.find(target => target.id === row.id)" :disabled="disabled" @update="update" /></div>
  </details></template></div>
</template>
