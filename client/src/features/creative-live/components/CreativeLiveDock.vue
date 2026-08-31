<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Activity, GitCompareArrows, RefreshCw, Radio, ScrollText, UsersRound } from "lucide-vue-next";
import { useAppStore } from "@/stores/app";
import { useCreativeLiveStore } from "../stores/creativeLive";
import ArtifactStatusRail from "./ArtifactStatusRail.vue";
import ExecutionTimeline from "./ExecutionTimeline.vue";
import LiveManuscript from "./LiveManuscript.vue";
import ReviewRail from "./ReviewRail.vue";
import RevisionDiff from "./RevisionDiff.vue";
import SessionTranscript from "./SessionTranscript.vue";

const app = useAppStore();
const live = useCreativeLiveStore();
const sideMode = ref<"review" | "session" | "revision">("review");
const artifacts = computed(() => live.snapshot?.artifacts || []);
const sessions = computed(() => live.snapshot?.sessions || []);
const latestActivity = computed(() => {
  const items = live.snapshot?.activity || [];
  return items.length ? items[items.length - 1] : null;
});

watch(() => app.currentProjectPath, (root) => { if (root) void live.connect(root); }, { immediate: true });

async function openSessionMode(): Promise<void> {
  sideMode.value = "session";
  const session = live.activeSession;
  if (session) await live.selectSession(session.session_id);
}

async function openRevisionMode(): Promise<void> {
  sideMode.value = "revision";
  await live.loadRevisions();
  const latest = live.revisions[0];
  if (latest) await live.loadRevision(latest.revision_id);
}

function shortName(path: string): string {
  return path.split(/[\\/]/).pop()?.replace(/\.(md|txt|json|ya?ml)$/i, "") || "候选产物";
}
</script>

<template>
  <section class="creative-live-dock" :data-status="live.snapshot?.status || 'idle'">
    <header class="creative-live-heading">
      <div class="creative-live-title">
        <span class="creative-live-signal"><Radio :size="14" /></span>
        <div><span>CREATIVE LIVE</span><h1>创作现场</h1><p>{{ live.snapshot?.active_task?.title || '等待下一项正式创作任务' }}</p></div>
      </div>
      <div class="creative-live-runtime">
        <i :class="{ live: live.connected && live.snapshot?.status === 'active' }"></i>
        <span>{{ live.snapshot?.status === 'active' ? '实时连接' : live.connected ? '已连接 · 当前待命' : '正在连接' }}</span>
        <button class="icon-button" title="重新连接创作现场" @click="live.connect(app.currentProjectPath)"><RefreshCw :size="14" /></button>
      </div>
    </header>

    <p v-if="live.error" class="creative-live-error">{{ live.error }}</p>

    <div class="creative-live-grid">
      <aside class="creative-live-left">
        <section class="creative-task-card">
          <span>当前任务</span>
          <strong>{{ live.snapshot?.active_task?.title || '等待任务' }}</strong>
          <p>{{ live.snapshot?.active_task?.message || '状态机会在领取下一项任务后，把正在处理的内容带到这里。' }}</p>
          <details v-if="live.snapshot?.active_task?.task_id"><summary>技术身份</summary><small>{{ live.snapshot.active_task.task_id }}</small></details>
        </section>
        <nav class="creative-artifact-list" aria-label="创作产物">
          <header><ScrollText :size="13" /><strong>现场产物</strong><span>{{ artifacts.length }}</span></header>
          <button v-for="artifact in artifacts" :key="artifact.artifact_id" :class="{ active: live.activeArtifact?.artifact_id === artifact.artifact_id }" @click="live.selectArtifact(artifact.artifact_id)">
            <i :data-identity="artifact.identity"></i><span><strong>{{ shortName(artifact.path) }}</strong><small>{{ artifact.identity === 'promoted' ? '已晋升' : artifact.identity === 'streaming_preview' ? '正在写' : '候选链' }}</small></span>
          </button>
          <p v-if="!artifacts.length">开始写作后，候选正文和修订稿会出现在这里。</p>
        </nav>
        <ArtifactStatusRail :identity="live.activeArtifact?.identity" :characters="live.activeArtifact?.characters || live.activeArtifact?.content.length" />
      </aside>

      <LiveManuscript :artifact="live.activeArtifact" />

      <aside class="creative-live-right">
        <nav class="creative-live-tabs">
          <button :class="{ active: sideMode === 'review' }" @click="sideMode = 'review'"><Activity :size="13" />审查</button>
          <button :class="{ active: sideMode === 'session' }" @click="openSessionMode"><UsersRound :size="13" />会话</button>
          <button :class="{ active: sideMode === 'revision' }" @click="openRevisionMode"><GitCompareArrows :size="13" />修订</button>
        </nav>
        <div class="creative-live-side-scroll">
          <template v-if="sideMode === 'review'">
            <ReviewRail :reviews="live.snapshot?.reviews" />
            <ExecutionTimeline :items="live.snapshot?.activity" />
          </template>
          <template v-else-if="sideMode === 'session'">
            <div v-if="sessions.length > 1" class="creative-session-selector">
              <button v-for="session in sessions" :key="session.session_id" :class="{ active: live.activeSession?.session_id === session.session_id }" @click="live.selectSession(session.session_id)">{{ session.role || 'Agent' }}</button>
            </div>
            <SessionTranscript :session="live.activeSession" />
          </template>
          <template v-else>
            <div v-if="live.revisions.length" class="creative-revision-selector">
              <button v-for="revision in live.revisions" :key="revision.revision_id" :class="{ active: live.selectedRevision?.revision_id === revision.revision_id }" @click="live.loadRevision(revision.revision_id)">{{ revision.identity === 'promoted' ? '正式晋升' : '候选修订' }} · {{ revision.characters.toLocaleString('zh-CN') }}</button>
            </div>
            <RevisionDiff :revision="live.selectedRevision" />
          </template>
        </div>
      </aside>
    </div>

    <footer class="creative-live-footer">
      <span><i></i>{{ latestActivity?.title || '等待创作信号' }}</span>
      <span>{{ Number(live.snapshot?.usage.total_tokens || 0).toLocaleString('zh-CN') }} Token · ${{ Number(live.snapshot?.usage.cost_usd || 0).toFixed(4) }}</span>
    </footer>
  </section>
</template>
