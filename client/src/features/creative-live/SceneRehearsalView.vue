<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import { ArrowDown, MessageCircleMore, RefreshCw, Waves } from "lucide-vue-next";
import { friendlyError, useAppStore } from "@/stores/app";
import { creativeLiveClient } from "./services/creativeLiveClient";
import { applyRehearsalTurn, rehearsalSpeakerSide, rehearsalTurnFromEvent } from "./sceneRehearsalProjection";
import type { CreativeLiveEvent, SceneRehearsalDetail, SceneRehearsalSummary } from "./types";

const app = useAppStore();
const scenes = ref<SceneRehearsalSummary[]>([]);
const selectedId = ref("");
const detail = shallowRef<SceneRehearsalDetail | null>(null);
const loading = ref(false);
const connected = ref(false);
const error = ref("");
const followLive = ref(true);
const chatScroll = ref<HTMLElement | null>(null);
const recentEvents = new Map<string, CreativeLiveEvent[]>();
let connection: ReturnType<typeof creativeLiveClient.observe> | null = null;
let generation = 0;

const liveScene = computed(() => scenes.value.find((item) => item.status === "creating") || null);
const selectedScene = computed(() => scenes.value.find((item) => item.transaction_id === selectedId.value) || null);
const turns = computed(() => detail.value?.turns || []);

watch(() => app.currentProjectPath, (root) => { void connect(root || ""); }, { immediate: true });
watch(() => detail.value?.turn_count, () => { if (followLive.value) void scrollToEnd(); });
onBeforeUnmount(disconnect);

function disconnect(): void {
  generation += 1;
  connection?.close();
  connection = null;
  connected.value = false;
  recentEvents.clear();
}

async function connect(root: string): Promise<void> {
  disconnect();
  scenes.value = [];
  detail.value = null;
  selectedId.value = "";
  if (!root) return;
  const current = generation;
  loading.value = true;
  error.value = "";
  try {
    await refreshIndex(root, current);
    if (current !== generation) return;
    connection = creativeLiveClient.observe(root, () => undefined, onEvent, (cause) => {
      if (current === generation) error.value = friendlyError(cause, "推演连接中断，请点刷新重连。");
    });
    connected.value = true;
  } catch (cause) {
    if (current === generation) error.value = friendlyError(cause, "暂时无法读取推演记录。");
  } finally {
    if (current === generation) loading.value = false;
  }
}

async function refreshIndex(root = app.currentProjectPath, current = generation): Promise<void> {
  if (!root) return;
  const response = await creativeLiveClient.rehearsals(root);
  if (current !== generation) return;
  scenes.value = response.scenes || [];
  const next = scenes.value.some((item) => item.transaction_id === selectedId.value)
    ? selectedId.value : (liveScene.value || scenes.value[0])?.transaction_id || "";
  if (next) await selectScene(next, next === liveScene.value?.transaction_id);
  else detail.value = null;
}

async function selectScene(id: string, live = false): Promise<void> {
  selectedId.value = id;
  followLive.value = live;
  const current = generation;
  const root = app.currentProjectPath;
  if (!root) return;
  try {
    const response = await creativeLiveClient.rehearsal(root, id);
    if (current !== generation || selectedId.value !== id) return;
    detail.value = (recentEvents.get(id) || []).reduce(applyRehearsalTurn, response.scene);
    await nextTick();
    if (followLive.value) void scrollToEnd();
    else if (chatScroll.value) chatScroll.value.scrollTop = 0;
  } catch (cause) {
    if (current === generation) error.value = friendlyError(cause, "这场推演记录暂时无法读取。");
  }
}

function onEvent(event: CreativeLiveEvent): void {
  const turn = rehearsalTurnFromEvent(event);
  const id = String(event.data.scene_transaction_id || "");
  if (!turn || !id) return;
  const previous = recentEvents.get(id) || [];
  recentEvents.set(id, [...previous.filter((item) => Number(item.data.turn) !== turn.turn), event].slice(-40));
  const known = scenes.value.find((item) => item.transaction_id === id);
  const updated: SceneRehearsalSummary = {
    transaction_id: id, scene_id: String(event.data.scene_id || known?.scene_id || ""),
    status: known?.status || "creating", objective: known?.objective || "正在推演当前场景",
    turn_count: Math.max(known?.turn_count || 0, turn.turn), updated_at: event.at,
  };
  scenes.value = [updated, ...scenes.value.filter((item) => item.transaction_id !== id)];
  if (selectedId.value === id && detail.value) detail.value = applyRehearsalTurn(detail.value, event);
  else if (!selectedId.value || followLive.value) void selectScene(id, true);
}

async function refresh(): Promise<void> {
  await connect(app.currentProjectPath || "");
}

async function scrollToEnd(): Promise<void> {
  await nextTick();
  chatScroll.value?.scrollTo({ top: chatScroll.value.scrollHeight, behavior: "smooth" });
}

function displayName(value: string): string { return value.split("/").at(-1) || value; }
function timeLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
</script>

<template>
  <section class="scene-rehearsal" aria-label="推演观察">
    <header class="scene-rehearsal-head">
      <div class="scene-rehearsal-brand"><span class="scene-rehearsal-mark"><MessageCircleMore :size="19" /></span><div><small>SCENE REHEARSAL</small><h1>推演观察</h1><p>人物说过的话，在这里按轮次留下。</p></div></div>
      <div class="scene-rehearsal-connection"><i :class="{ active: connected }"></i><span>{{ connected ? '实时接收' : '历史记录' }}</span><button type="button" title="刷新推演记录" @click="refresh"><RefreshCw :size="15" /></button></div>
    </header>
    <p v-if="error" class="scene-rehearsal-error" role="alert">{{ error }}</p>
    <div class="scene-rehearsal-layout">
      <aside class="scene-rehearsal-list" aria-label="推演场景历史">
        <div class="scene-rehearsal-list-head"><span>场景记录</span><strong>{{ scenes.length }}</strong></div>
        <button v-if="liveScene && selectedId !== liveScene.transaction_id" type="button" class="scene-rehearsal-back-live" @click="selectScene(liveScene.transaction_id, true)"><Waves :size="15" />返回正在推演的场景</button>
        <button v-for="item in scenes" :key="item.transaction_id" type="button" class="scene-rehearsal-scene" :class="{ active: selectedId === item.transaction_id }" @click="selectScene(item.transaction_id, item.status === 'creating')">
          <span class="scene-rehearsal-scene-top"><strong>{{ item.scene_id }}</strong><em v-if="item.status === 'creating'">进行中</em></span>
          <span class="scene-rehearsal-objective">{{ item.objective }}</span>
          <small>{{ item.turn_count }} 轮对戏 <span>{{ timeLabel(item.updated_at) }}</span></small>
        </button>
        <p v-if="!scenes.length && !loading" class="scene-rehearsal-list-empty">还没有场景推演。开始创作后，第一轮角色回应会出现在这里。</p>
      </aside>
      <main class="scene-rehearsal-stage">
        <template v-if="selectedScene">
          <div class="scene-rehearsal-stage-head"><div><small>{{ selectedScene.scene_id }} / 排练记录</small><h2>{{ selectedScene.objective }}</h2></div><span :class="{ active: selectedScene.status === 'creating' }">{{ selectedScene.status === 'creating' ? '正在发生' : '历史回看' }}</span></div>
          <div ref="chatScroll" class="scene-rehearsal-chat" role="log" aria-live="polite" aria-relevant="additions">
            <div v-if="detail?.environment.length" class="scene-rehearsal-atmosphere"><span>空间底色</span><p v-for="(passage, index) in detail.environment" :key="`${passage.beat_id}-${index}`">{{ passage.description }}</p></div>
            <div v-for="turn in turns" :key="turn.turn" class="scene-rehearsal-turn" :class="rehearsalSpeakerSide(turns, turn.speaker)">
              <div class="scene-rehearsal-turn-meta"><span>{{ displayName(turn.speaker) }}</span><small>第 {{ turn.turn }} 轮 · {{ turn.beat_id }}</small></div>
              <div v-if="!turn.entries.length" class="scene-rehearsal-silence">这一轮，{{ displayName(turn.speaker) }}没有开口，也没有动作。</div>
              <div v-for="entry in turn.entries" :key="entry.entry_id" class="scene-rehearsal-message"><span class="scene-rehearsal-avatar">{{ displayName(turn.speaker).slice(0, 1) }}</span><div class="scene-rehearsal-bubble"><p v-if="entry.spoken" class="scene-rehearsal-spoken">{{ entry.spoken }}</p><p v-if="entry.first_person_action" class="scene-rehearsal-action">{{ entry.first_person_action }}</p></div></div>
            </div>
            <div v-if="!turns.length" class="scene-rehearsal-waiting"><MessageCircleMore :size="24" /><strong>{{ selectedScene.status === 'creating' ? '等待角色进入这一场' : '这场尚无可回看的角色轮次' }}</strong><span>角色完成一轮后，发言和可见动作会一起出现。</span></div>
          </div>
          <button v-if="followLive && turns.length" class="scene-rehearsal-scroll" type="button" @click="scrollToEnd"><ArrowDown :size="14" />最新一轮</button>
        </template>
        <div v-else class="scene-rehearsal-blank"><Waves :size="28" /><h2>推演还没开始</h2><p>这里会保留角色之间的真实轮次，也能回看已经完成的场景。</p></div>
      </main>
    </div>
  </section>
</template>
