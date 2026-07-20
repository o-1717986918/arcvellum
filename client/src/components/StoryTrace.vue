<script setup lang="ts">
import { computed } from "vue";
import { asList, asRecord, describeWorkflowAction, labelFor, targetLabel } from "@/services/presentation";

const props = defineProps<{ dashboard: Record<string, unknown> | null }>();

const actions = computed(() => asList<Record<string, unknown>>(props.dashboard?.next_actions).slice(0, 7));
const events = computed(() => asList<Record<string, unknown>>(props.dashboard?.recent_events).slice(-4));
</script>

<template>
  <section class="story-trace" aria-label="创作脉络">
    <header>
      <div><span class="eyebrow">正在生长的故事脉络</span><h2>下一步从哪里发生</h2></div>
      <span class="live-pill"><i></i>实时观察</span>
    </header>
    <div v-if="actions.length" class="trace-map">
      <div v-for="(action, index) in actions" :key="`${action.route}-${index}`" class="trace-node" :class="{ active: index === 0 }">
        <span class="node-index">{{ String(index + 1).padStart(2, "0") }}</span>
        <div>
          <small>{{ labelFor(action.route) }}</small>
          <strong>{{ targetLabel(action.target) }}</strong>
          <p>{{ describeWorkflowAction(action.next_action || action.current_step) }}</p>
        </div>
      </div>
    </div>
    <div v-else class="trace-empty">
      <span class="trace-seed"></span>
      <div><strong>创作脉络正在等待第一项任务</strong><p>补充作品方向后，新的节点会在这里出现。</p></div>
    </div>
    <footer v-if="events.length">
      <span>最近变化</span>
      <p>{{ asRecord(events.at(-1)?.payload).message || events.at(-1)?.event || "项目状态已更新" }}</p>
    </footer>
  </section>
</template>
