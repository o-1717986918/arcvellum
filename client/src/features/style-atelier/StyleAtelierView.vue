<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  BookCopy,
  CircleAlert,
  Fingerprint,
  Gauge,
  LibraryBig,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-vue-next";
import StyleJourney from "./components/StyleJourney.vue";
import StyleEngineeringConsole from "./components/StyleEngineeringConsole.vue";
import StyleSourceRail from "./components/StyleSourceRail.vue";
import StyleSourceWorkshop from "./components/StyleSourceWorkshop.vue";
import StyleVersionRack from "./components/StyleVersionRack.vue";
import { useStyleAtelierStore } from "./stores/styleAtelier";
import type {
  StyleAuthorCreatePayload,
  StyleSourceCreatePayload,
  StyleWorkCreatePayload,
} from "./types";
import "./styleAtelier.css";

const style = useStyleAtelierStore();
const sourceWorkshopOpen = ref(false);

const summary = computed(() => style.workbench?.summary);
const selectedSources = computed(() => style.selectedWork?.sources || []);
const sourceCharacters = computed(() =>
  selectedSources.value.reduce((sum, item) => sum + Number(item.character_count || 0), 0),
);
const evaluation = computed(() => style.versionDetail?.evaluation || style.selectedVersion?.evaluations?.[0] || {});
const integrity = computed(() => String((style.versionDetail?.integrity as Record<string, unknown> | undefined)?.status || ""));
const promptQuality = computed(() => style.versionDetail?.prompt_quality || style.selectedVersion?.prompt_quality || {});

onMounted(() => void load());
onBeforeUnmount(style.disposeEngineeringStream);
watch(() => style.projectRoot, () => void load());

async function load(): Promise<void> {
  try {
    await style.load();
  } catch {
    // The store exposes an actionable error state.
  }
}

async function createAuthor(payload: StyleAuthorCreatePayload): Promise<void> {
  try {
    await style.createAuthor(payload);
    sourceWorkshopOpen.value = false;
  } catch {
    // The store keeps the transaction failure visible.
  }
}

async function createWork(payload: StyleWorkCreatePayload): Promise<void> {
  try {
    await style.createWork(payload);
    sourceWorkshopOpen.value = false;
  } catch {
    // The store keeps the transaction failure visible.
  }
}

async function importSource(payload: StyleSourceCreatePayload): Promise<void> {
  try {
    await style.importSource(payload);
    sourceWorkshopOpen.value = false;
  } catch {
    // The store keeps the transaction failure visible.
  }
}

function compactNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

function issueLabel(issue: string): string {
  if (issue.includes("library is unavailable")) return "公共文风资料库尚未建立；作品内版本仍可继续使用。";
  if (issue.includes("integrity")) return "有文风版本未通过完整性检查，请打开对应版本查看证据。";
  return "部分文风资料需要重新检查。";
}

function verdictLabel(value: unknown): string {
  const labels: Record<string, string> = {
    pass: "通过",
    clear: "未发现泄漏",
    low: "低风险",
    medium: "中等风险",
    high: "高风险",
  };
  return labels[String(value || "")] || "等待结果";
}
</script>

<template>
  <div class="view style-atelier-view">
    <header class="style-atelier-heading">
      <div>
        <span class="eyebrow">文风工坊</span>
        <h1>把作品语感变成可追溯的创作约束</h1>
        <p>从合法来源中抽象写作规律，经隔离评测与独立审查形成版本，再明确挂载到当前作品。</p>
      </div>
      <div class="style-heading-actions">
        <button class="style-refresh" :disabled="style.busy" title="重新读取文风工坊" @click="load">
          <RefreshCw :size="16" :class="{ spinning: style.busy }" />
          <span>{{ style.busy ? "正在同步" : "同步状态" }}</span>
        </button>
        <button class="style-primary-action" title="登记作者、作品或来源文本" @click="sourceWorkshopOpen = true">
          <LibraryBig :size="16" />
          <span>登记来源</span>
        </button>
      </div>
    </header>

    <div v-if="style.error" class="style-message danger" role="alert">
      <CircleAlert :size="16" />
      <span>{{ style.error }}</span>
      <button @click="style.clearError">关闭</button>
    </div>
    <div v-if="style.notice" class="style-message success" role="status">
      <ShieldCheck :size="16" />
      <span>{{ style.notice }}</span>
      <button @click="style.clearNotice">关闭</button>
    </div>

    <section v-if="style.workbench" class="style-atelier-shell">
      <header class="style-atelier-instrument">
        <div class="style-instrument-title">
          <span class="style-sigil"><Fingerprint :size="19" /></span>
          <span><small>Evidence loom</small><strong>文风证据织机</strong></span>
        </div>
        <div class="style-summary-strip">
          <span><strong>{{ summary?.source_count || 0 }}</strong><small>来源</small></span>
          <span><strong>{{ compactNumber(summary?.source_character_count || 0) }}</strong><small>汉字证据</small></span>
          <span><strong>{{ summary?.reviewed_count || 0 }}</strong><small>已审版本</small></span>
          <span :data-live="Boolean(style.activeMount.style_id)"><strong>{{ style.activeMount.style_id ? "已挂载" : "未挂载" }}</strong><small>当前作品</small></span>
        </div>
      </header>

      <StyleJourney :stages="style.workbench.journey" />
      <StyleEngineeringConsole
        :authors="style.authors"
        :selected-author-id="style.selectedAuthorId"
        :selected-version="style.selectedVersion"
        :job="style.engineeringJob"
        :task="style.engineeringTask"
        :events="style.engineeringEvents"
        :busy="style.engineeringBusy"
        :stream-error="style.engineeringStreamError"
        @compile="style.compileProfile"
        @advance="style.advanceProfile"
        @build="style.buildProfile"
        @approve-writeback="style.approveWriteback"
        @reject-writeback="style.rejectWriteback"
        @retry="style.retryEngineering"
        @stop="style.stopEngineering"
      />

      <div class="style-atelier-grid">
        <StyleSourceRail
          :authors="style.authors"
          :selected-author-id="style.selectedAuthorId"
          :selected-work-id="style.selectedWorkId"
          @select-author="style.selectAuthor"
          @select-work="style.selectWork"
        />

        <main class="style-evidence-field">
          <section v-if="style.selectedAuthor" class="style-evidence-identity">
            <div>
              <span class="style-section-label">当前语料焦点</span>
              <h2>{{ style.selectedAuthor.name }}</h2>
              <p>{{ style.selectedWork?.title || "尚未选择作品" }}<template v-if="style.selectedWork?.year"> · {{ style.selectedWork.year }}</template></p>
            </div>
            <div class="style-evidence-count">
              <BookCopy :size="17" />
              <span><strong>{{ selectedSources.length }}</strong><small>份文本 · {{ compactNumber(sourceCharacters) }} 字</small></span>
            </div>
          </section>

          <section v-if="selectedSources.length" class="style-source-table">
            <header><span>来源证据</span><small>只展示身份与统计，不回显原文</small></header>
            <article v-for="source in selectedSources" :key="source.source_id">
              <span class="style-source-mark"><BookCopy :size="14" /></span>
              <span><strong>{{ source.filename || source.source_id }}</strong><small>{{ source.chunk_count }} 个分析片段</small></span>
              <span><strong>{{ compactNumber(source.character_count) }}</strong><small>汉字</small></span>
              <i :title="source.content_sha256">已固化</i>
            </article>
          </section>

          <section v-else class="style-evidence-empty">
            <Sparkles :size="26" />
            <strong>从可靠来源开始</strong>
            <p>作者与作品建立后，导入文本会在这里形成不回显原文的证据谱系。</p>
          </section>

          <section v-if="style.selectedVersion" class="style-version-evidence">
            <header>
              <div><span class="style-section-label">版本证据</span><h2>{{ style.selectedVersion.display_name || style.selectedVersion.profile_id }}</h2></div>
              <span class="style-integrity" :data-state="integrity || style.selectedVersion.state">
                <ShieldCheck :size="14" />{{ integrity === "pass" ? "完整性通过" : style.selectedVersion.state === "conflict" ? "存在冲突" : "证据处理中" }}
              </span>
            </header>
            <div class="style-evidence-metrics">
              <article><Gauge :size="17" /><span><small>隔离评测</small><strong>{{ evaluation.overall_score ?? "待评测" }}</strong></span></article>
              <article><ShieldCheck :size="17" /><span><small>泄漏风险</small><strong>{{ verdictLabel(evaluation.leakage_risk_status || evaluation.risk_level) }}</strong></span></article>
              <article><BookCopy :size="17" /><span><small>提示词细节</small><strong>{{ promptQuality.detail_chars ? `${promptQuality.detail_chars} 字` : "待编译" }}</strong></span></article>
            </div>
            <p class="style-copy-boundary">{{ style.versionDetail?.copy_boundary || "版本只保存抽象后的写作约束，不向正文任务回传来源原文。" }}</p>
          </section>
        </main>

        <StyleVersionRack
          :versions="style.versions"
          :active-mount="style.activeMount"
          :selected-key="style.selectedVersionKey"
          @select="style.selectVersion"
        />
      </div>

      <footer v-if="style.workbench.issues.length" class="style-atelier-issues">
        <CircleAlert :size="15" />
        <span>{{ issueLabel(style.workbench.issues[0]) }}</span>
      </footer>
    </section>

    <section v-else class="style-page-state">
      <Fingerprint :size="28" />
      <strong>{{ style.busy ? "正在整理文风证据" : "文风工坊还没有准备好" }}</strong>
      <p>{{ style.busy ? "正在核对来源、评测、版本与当前挂载。" : "请先选择一部作品，再重新同步。" }}</p>
    </section>

    <StyleSourceWorkshop
      v-if="sourceWorkshopOpen"
      :authors="style.authors"
      :selected-author-id="style.selectedAuthorId"
      :selected-work-id="style.selectedWorkId"
      :busy="style.authoringBusy"
      @close="sourceWorkshopOpen = false"
      @create-author="createAuthor"
      @create-work="createWork"
      @import-source="importSource"
    />
  </div>
</template>
