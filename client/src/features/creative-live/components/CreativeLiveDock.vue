<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { Activity, GitCompareArrows, RefreshCw, Radio, ScrollText } from "lucide-vue-next";
import { useAppStore } from "@/stores/app";
import { useCreativeLiveStore } from "../stores/creativeLive";
import ArtifactStatusRail from "./ArtifactStatusRail.vue";
import CreativeProcessView from "./CreativeProcessView.vue";
import CreativeRevisionView from "./CreativeRevisionView.vue";
import LiveManuscript from "./LiveManuscript.vue";
import ReviewRail from "./ReviewRail.vue";
import SceneTransactionPulse from "./SceneTransactionPulse.vue";
import { artifactKindLabel, artifactStatusLabel, artifactTitle } from "../artifactPresentation";
import { activityTitle } from "../creativePresentation";

const app = useAppStore();
const live = useCreativeLiveStore();
const mainMode = ref<"process" | "manuscript" | "revision">("process");
const mainCanvas = ref<HTMLElement | null>(null);
const artifacts = computed(() => live.snapshot?.artifacts || []);
const sessions = computed(() => live.snapshot?.sessions || []);
const latestActivity = computed(() => {
  const items = live.snapshot?.activity || [];
  return items.length ? items[items.length - 1] : null;
});

watch(() => app.currentProjectPath, (root) => { if (root) void live.connect(root); }, { immediate: true });
onBeforeUnmount(() => live.disconnect());

function openArtifact(artifactId: string): void {
  live.selectArtifact(artifactId);
  showMain("manuscript");
}

async function openRevisionMode(): Promise<void> {
  showMain("revision");
  await live.loadRevisions();
  const latest = live.revisions.at(-1);
  if (latest) await live.loadRevision(latest.revision_id);
  if (window.matchMedia("(max-width: 620px)").matches) {
    await nextTick();
    mainCanvas.value?.querySelector(".revision-diff-scroll p.added, .revision-diff-scroll p.removed")?.scrollIntoView({ block: "nearest" });
  }
}

function showMain(mode: "process" | "manuscript" | "revision"): void {
  mainMode.value = mode;
  if (window.matchMedia("(max-width: 620px)").matches) {
    void nextTick(() => mainCanvas.value?.scrollIntoView({ block: "start" }));
  }
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
        <button class="icon-button" title="重新连接创作现场" @click="live.reconnect(app.currentProjectPath)"><RefreshCw :size="14" /></button>
      </div>
    </header>

    <p v-if="live.error" class="creative-live-error">{{ live.error }}</p>

    <SceneTransactionPulse :transaction="live.snapshot?.active_scene_transaction" />

    <section v-if="live.snapshot?.style_provenance" class="creative-style-provenance" aria-label="本场文风来源">
      <strong>本场表达参考</strong>
      <span>{{ live.snapshot.style_provenance.scene_id || '当前场景' }} · {{ live.snapshot.style_provenance.reference_ids.join(' + ') || '中性原则' }}</span>
      <small v-if="live.snapshot.style_provenance.technique_axes.length">技法轴：{{ live.snapshot.style_provenance.technique_axes.join('、') }}</small>
      <details><summary>版本与选择依据</summary><small>文风版本 {{ live.snapshot.style_provenance.style_version_id || '未挂载' }} · {{ live.snapshot.style_provenance.selector_version }} · {{ live.snapshot.style_provenance.selection_digest.slice(0, 12) }}</small></details>
    </section>

    <div class="creative-live-grid">
      <aside class="creative-live-left">
        <section class="creative-task-card">
          <span>当前任务</span>
          <strong>{{ live.snapshot?.active_task?.title || '等待任务' }}</strong>
          <p>{{ live.snapshot?.active_task?.message || '状态机会在领取下一项任务后，把正在处理的内容带到这里。' }}</p>
          <details v-if="live.snapshot?.active_task?.task_id"><summary>技术身份</summary><small>{{ live.snapshot.active_task.task_id }}</small></details>
        </section>
        <nav class="creative-artifact-list" aria-label="创作产物">
          <header><ScrollText :size="13" /><strong>创作内容</strong><span>{{ artifacts.length }}</span></header>
          <button v-for="artifact in artifacts" :key="artifact.artifact_id" :class="{ active: live.activeArtifact?.artifact_id === artifact.artifact_id }" @click="openArtifact(artifact.artifact_id)">
            <i :data-identity="artifact.identity" :data-kind="artifact.kind"></i><span><strong>{{ artifactTitle(artifact) }}</strong><small>{{ artifactKindLabel(artifact) }} · {{ artifactStatusLabel(artifact) }}</small></span>
          </button>
          <p v-if="!artifacts.length">人物、世界观、规划、审查意见和正文形成后，都会在这里留下可阅读的现场记录。</p>
        </nav>
        <ArtifactStatusRail :identity="live.activeArtifact?.identity" :characters="live.activeArtifact?.characters || live.activeArtifact?.content.length" :kind="live.activeArtifact?.kind" />
      </aside>

      <main ref="mainCanvas" class="creative-live-main">
        <nav class="creative-main-tabs" aria-label="创作现场主视图">
          <button :class="{ active: mainMode === 'process' }" @click="showMain('process')"><Activity :size="14" />创作过程</button>
          <button :class="{ active: mainMode === 'manuscript' }" @click="showMain('manuscript')"><ScrollText :size="14" />正文与资料</button>
          <button :class="{ active: mainMode === 'revision' }" @click="openRevisionMode"><GitCompareArrows :size="14" />正文修订</button>
        </nav>
        <CreativeProcessView v-if="mainMode === 'process'" :activity="live.snapshot?.activity" :events="live.snapshot?.events" :sessions="sessions" :selected-session="live.activeSession" :project-root="app.currentProjectPath" :transaction-id="live.snapshot?.active_scene_transaction?.transaction_id" @select-session="live.selectSession" />
        <LiveManuscript v-else-if="mainMode === 'manuscript'" :artifact="live.activeArtifact" />
        <CreativeRevisionView v-else :artifact="live.activeArtifact" :revisions="live.revisions" :selected-revision="live.selectedRevision" :comparison-revision="live.comparisonRevision" @select-revision="live.loadRevision" />
      </main>

      <aside class="creative-live-right">
        <header class="creative-live-side-heading"><Activity :size="13" />审查与复核</header>
        <div class="creative-live-side-scroll">
          <ReviewRail :reviews="live.snapshot?.reviews" />
        </div>
      </aside>
    </div>

    <footer class="creative-live-footer">
      <span><i></i>{{ latestActivity ? activityTitle(latestActivity) : '等待创作信号' }}</span>
      <span>{{ Number(live.snapshot?.usage.total_tokens || 0).toLocaleString('zh-CN') }} Token · ${{ Number(live.snapshot?.usage.cost_usd || 0).toFixed(4) }}</span>
    </footer>
  </section>
</template>
