<script setup lang="ts">
import { computed } from "vue";
import { Activity, ChevronRight, CircleAlert, CircleCheck, ClipboardCheck, ShieldCheck } from "lucide-vue-next";
import { asList, asRecord, describeGate, labelFor } from "@/services/presentation";

const props = defineProps<{ dashboard: Record<string, unknown> | null; expanded: boolean }>();
const emit = defineEmits<{ toggle: [] }>();

const summary = computed(() => asRecord(props.dashboard?.summary));
const audits = computed(() => asList<Record<string, unknown>>(props.dashboard?.route_audits));
const readyCount = computed(() => audits.value.filter((audit) => Number(audit.blocking_count || 0) === 0).length);
const blockingCount = computed(() => Number(summary.value.blocking_count || 0));
const pendingCount = computed(() => Number(summary.value.pending_task_count || 0));

function auditMessage(audit: Record<string, unknown>): string {
  if (!Number(audit.blocking_count || 0)) return "这一条路线具备继续推进的条件。";
  const top = asRecord(asList<Record<string, unknown>>(audit.top_blocking_gates)[0]);
  return describeGate(top.message) || "还有需要补齐的正式证据。";
}
</script>

<template>
  <aside class="narrative-health-rail" :class="{ expanded }" aria-label="作品健康轨">
    <button class="narrative-health-trigger" :aria-expanded="expanded" title="展开作品健康轨" @click="emit('toggle')">
      <span class="rail-orb" :class="{ warning: blockingCount }"><ShieldCheck :size="18" /></span>
      <span class="rail-signal" :class="{ warning: blockingCount }"></span>
    </button>
    <section class="narrative-health-drawer" :aria-hidden="!expanded">
      <header>
        <div><span>WORK HEALTH</span><strong>作品健康</strong></div>
        <button class="rail-close" title="收起健康轨" @click="emit('toggle')"><ChevronRight :size="16" /></button>
      </header>
      <dl class="health-rail-metrics">
        <div><dt><CircleCheck :size="13" />可推进</dt><dd>{{ readyCount }}/{{ audits.length }}</dd></div>
        <div :class="{ warning: pendingCount }"><dt><ClipboardCheck :size="13" />待处理</dt><dd>{{ pendingCount }}</dd></div>
        <div :class="{ warning: blockingCount }"><dt><CircleAlert :size="13" />需补齐</dt><dd>{{ blockingCount }}</dd></div>
      </dl>
      <div class="health-rail-list">
        <article v-for="audit in audits.slice(0, 5)" :key="String(audit.route)" :class="{ blocked: Number(audit.blocking_count || 0) }">
          <i><Activity :size="11" /></i>
          <div><strong>{{ labelFor(audit.route) }}</strong><p>{{ auditMessage(audit) }}</p></div>
        </article>
      </div>
    </section>
  </aside>
</template>
