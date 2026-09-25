<script setup lang="ts">
import { computed, shallowRef, watch } from "vue";
import { Activity, MessageCircleMore, UsersRound } from "lucide-vue-next";
import { creativeLiveClient } from "../services/creativeLiveClient";
import type { CreativeActivity, CreativeLiveEvent, CreativeSession, SceneRehearsalDetail } from "../types";
import { sessionDisplayName } from "../creativePresentation";
import ExecutionTimeline from "./ExecutionTimeline.vue";
import SessionTranscript from "./SessionTranscript.vue";

const props = defineProps<{
  activity?: CreativeActivity[];
  events?: CreativeLiveEvent[];
  sessions?: CreativeSession[];
  selectedSession?: CreativeSession | null;
  projectRoot: string;
  transactionId?: string;
}>();
const emit = defineEmits<{ selectSession: [sessionId: string] }>();
const visibleSessions = computed(() => (props.sessions || []).filter((item) => item.transcript || item.tools?.length));
const activeSession = computed(() => {
  const selected = props.selectedSession;
  return visibleSessions.value.find((item) => item.session_id === selected?.session_id) || visibleSessions.value[0] || null;
});
const rehearsal = shallowRef<SceneRehearsalDetail | null>(null);
const latestTurn = computed(() => (props.events || []).filter((item) =>
  item.event === "scene.performance.interaction.turn" && item.data.scene_transaction_id === props.transactionId,
).at(-1)?.sequence || 0);
let loadGeneration = 0;

watch(() => [props.projectRoot, props.transactionId, latestTurn.value], async () => {
  const generation = ++loadGeneration;
  rehearsal.value = null;
  if (!props.projectRoot || !props.transactionId) return;
  try {
    const response = await creativeLiveClient.rehearsal(props.projectRoot, props.transactionId);
    if (generation === loadGeneration) rehearsal.value = response.scene;
  } catch {
    if (generation === loadGeneration) rehearsal.value = null;
  }
}, { immediate: true });

function selectSession(event: Event): void {
  const id = (event.target as HTMLSelectElement).value;
  if (id) emit("selectSession", id);
}

function timeLabel(value?: string): string {
  const date = new Date(value || "");
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
</script>

<template>
  <section class="creative-process-view" aria-label="创作过程">
    <div class="creative-process-scroll">
      <header class="creative-process-heading">
        <span><Activity :size="14" />创作过程</span>
        <h2>看见每一步怎样写成正文</h2>
        <p>{{ visibleSessions.length }} 次 Agent 工作 · {{ activity?.length || 0 }} 条进度记录</p>
      </header>

      <section class="creative-process-work">
        <div class="creative-process-section-title"><UsersRound :size="14" /><strong>Agent 工作结果</strong></div>
        <label v-if="visibleSessions.length" class="creative-process-selector">
          <span>选择一次创作行为</span>
          <select :value="activeSession?.session_id" aria-label="选择创作行为" @change="selectSession">
            <option v-for="(session, index) in visibleSessions" :key="session.session_id" :value="session.session_id">
              {{ sessionDisplayName(session, index) }} · {{ timeLabel(session.updated_at) }}
            </option>
          </select>
        </label>
        <SessionTranscript v-if="activeSession" :session="activeSession" />
        <p v-else class="creative-process-empty">规划、角色演出、环境描写与主创审读开始后，会在这里留下可读结果。</p>
      </section>

      <section v-if="rehearsal?.turns.length || rehearsal?.environment.length" class="creative-process-rehearsal">
        <div class="creative-process-section-title"><MessageCircleMore :size="14" /><strong>角色与场景推演</strong><small>{{ rehearsal?.turn_count || 0 }} 轮</small></div>
        <div v-for="turn in rehearsal?.turns || []" :key="turn.turn" class="creative-process-turn">
          <header><strong>{{ turn.speaker }}</strong><span>第 {{ turn.turn }} 轮</span></header>
          <div v-for="entry in turn.entries" :key="entry.entry_id">
            <p v-if="entry.spoken" class="creative-process-spoken">{{ entry.spoken }}</p>
            <p v-if="entry.first_person_action" class="creative-process-action">{{ entry.first_person_action }}</p>
          </div>
        </div>
        <details v-if="rehearsal?.environment.length" class="creative-process-environment">
          <summary>环境 Agent 原始描写 · {{ rehearsal.environment.length }} 段</summary>
          <p v-for="(passage, index) in rehearsal.environment" :key="`${passage.beat_id}-${index}`">{{ passage.description }}</p>
        </details>
      </section>

      <ExecutionTimeline :items="activity" />
    </div>
  </section>
</template>
