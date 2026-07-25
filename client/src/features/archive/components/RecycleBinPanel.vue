<script setup lang="ts">
import { ArchiveRestore, RotateCcw } from "lucide-vue-next";
import type { RecycleEntry } from "../types";

defineProps<{ items: RecycleEntry[]; busy?: boolean; reason: string }>();
const emit = defineEmits<{ restore: [item: RecycleEntry]; "update:reason": [value: string] }>();
</script>

<template>
  <section class="archive-recycle-panel">
    <header><ArchiveRestore :size="17" /><div><h2>项目回收站</h2><p>归档不会删除历史快照。恢复前仍会检查正式位置是否冲突。</p></div></header>
    <label><span>恢复原因</span><input :value="reason" placeholder="说明为什么恢复这份资料" @input="emit('update:reason', ($event.target as HTMLInputElement).value)" /></label>
    <div v-if="items.length" class="archive-recycle-list">
      <article v-for="item in items" :key="item.entry_id">
        <div><span>{{ item.asset_type }}</span><strong>{{ item.title || item.asset_id }}</strong><p>{{ item.reason || "作者归档的作品资料" }}</p></div>
        <button :disabled="busy || !reason.trim()" @click="emit('restore', item)"><RotateCcw :size="14" />恢复</button>
      </article>
    </div>
    <p v-else class="archive-panel-empty">项目回收站是空的。</p>
  </section>
</template>
