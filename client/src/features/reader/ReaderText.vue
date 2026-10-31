<script setup lang="ts">
import { computed } from "vue";
const props = defineProps<{ text: string; query: string }>();
const parts = computed(() => {
  const needle = props.query.trim().toLocaleLowerCase();
  if (!needle) return [{ text: props.text, match: false }];
  const source = props.text.toLocaleLowerCase();
  const result: Array<{ text: string; match: boolean }> = [];
  let start = 0, found = source.indexOf(needle);
  while (found !== -1) {
    result.push({ text: props.text.slice(start, found), match: false });
    result.push({ text: props.text.slice(found, found + needle.length), match: true });
    start = found + needle.length;
    found = source.indexOf(needle, start);
  }
  result.push({ text: props.text.slice(start), match: false });
  return result;
});
</script>
<template><template v-for="(part, index) in parts" :key="index"><mark v-if="part.match">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></template>
