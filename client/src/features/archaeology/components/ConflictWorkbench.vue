<script setup lang="ts">
import { CircleAlert, CircleCheck, GitCompareArrows } from "lucide-vue-next";
import type { ArchaeologyConflicts } from "../types";

defineProps<{ conflicts: ArchaeologyConflicts }>();

function dispositionLabel(value: string): string {
  return {
    resolved: "已有结论",
    not_applicable: "无需处理",
    keep_distinct: "保留差异",
    unresolved: "等待判断",
    unreviewed: "尚未复核",
  }[value] || "等待判断";
}
</script>

<template>
  <section class="archaeology-conflict-board">
    <header>
      <span><GitCompareArrows :size="15" />冲突与多种解释</span>
      <small :data-alert="conflicts.unresolved_count > 0">{{ conflicts.unresolved_count }} 项未闭合</small>
    </header>
    <div v-if="conflicts.items.length" class="archaeology-conflict-list">
      <article v-for="conflict in conflicts.items" :key="conflict.index" :data-open="!['resolved', 'not_applicable'].includes(conflict.disposition)">
        <span>
          <CircleCheck v-if="['resolved', 'not_applicable'].includes(conflict.disposition)" :size="15" />
          <CircleAlert v-else :size="15" />
        </span>
        <div>
          <strong>{{ conflict.summary || "原作中存在需要进一步判断的差异" }}</strong>
          <small>{{ dispositionLabel(conflict.disposition) }} · {{ conflict.evidence_refs.length }} 条来源证据</small>
          <p v-if="conflict.rationale">{{ conflict.rationale }}</p>
        </div>
      </article>
    </div>
    <div v-else class="archaeology-panel-empty">
      当前没有发现需要并列保留的冲突解释。
    </div>
  </section>
</template>
