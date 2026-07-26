<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  Archive,
  BookOpenText,
  CircleAlert,
  FileArchive,
  Fingerprint,
  GitCompareArrows,
  Layers3,
  Plus,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
} from "lucide-vue-next";
import { useAppStore } from "@/stores/app";
import ArchaeologyExtractionConsole from "./components/ArchaeologyExtractionConsole.vue";
import ArchaeologyJourney from "./components/ArchaeologyJourney.vue";
import ConflictWorkbench from "./components/ConflictWorkbench.vue";
import EntityResolutionBoard from "./components/EntityResolutionBoard.vue";
import PromotionQueue from "./components/PromotionQueue.vue";
import ReconstructionPreview from "./components/ReconstructionPreview.vue";
import SegmentationTimeline from "./components/SegmentationTimeline.vue";
import SourceImportPanel from "./components/SourceImportPanel.vue";
import { useArchaeologyStore } from "./stores/archaeology";
import type { ArchaeologyImportForm } from "./types";
import "./archaeology.css";

const app = useAppStore();
const archaeology = useArchaeologyStore();
const importOpen = ref(false);
const activePane = ref<"reconstruction" | "entities" | "conflicts" | "sources">("reconstruction");

const workbench = computed(() => archaeology.workbench);
const modeIntent = computed(() => workbench.value?.mode.intent || "");
const analysisOnly = computed(() => workbench.value?.mode.id === "analysis");
const progress = computed(() => {
  const stages = workbench.value?.journey || [];
  return stages.length
    ? Math.round((stages.filter((stage) => stage.status === "complete").length / stages.length) * 100)
    : 0;
});

const panes = [
  { id: "reconstruction", label: "项目重建", icon: Layers3 },
  { id: "entities", label: "人物与别名", icon: Fingerprint },
  { id: "conflicts", label: "冲突", icon: GitCompareArrows },
  { id: "sources", label: "来源结构", icon: BookOpenText },
] as const;

onMounted(() => void archaeology.load());
watch(() => app.currentProjectPath, () => void archaeology.load());
onBeforeUnmount(() => archaeology.reset());

async function importSource(file: File, form: ArchaeologyImportForm): Promise<void> {
  try {
    await archaeology.importSource(file, form);
    importOpen.value = false;
  } catch {
    // The store owns the user-facing error and keeps the dialog open.
  }
}

function closeMessage(kind: "error" | "notice"): void {
  if (kind === "error") archaeology.error = "";
  else archaeology.notice = "";
}
</script>

<template>
  <div class="archaeology-view">
    <header class="archaeology-heading">
      <div>
        <span class="context-label">Project Archaeology</span>
        <h1>从一部旧作，恢复可继续创作的项目</h1>
        <p>原文、推断和正式设定彼此分开；每项结论都保留证据、置信度与未决冲突。</p>
      </div>
      <div class="archaeology-heading-actions">
        <button class="archaeology-refresh" :disabled="archaeology.busy" title="同步作品考古状态" @click="archaeology.refresh">
          <RefreshCw :size="15" :class="{ spinning: archaeology.busy }" />同步
        </button>
        <button class="archaeology-primary" @click="importOpen = true"><Plus :size="15" />导入已有作品</button>
      </div>
    </header>

    <div v-if="archaeology.error" class="archaeology-message danger" role="alert">
      <CircleAlert :size="15" /><span>{{ archaeology.error }}</span><button @click="closeMessage('error')">关闭</button>
    </div>
    <div v-if="archaeology.notice" class="archaeology-message success">
      <ShieldCheck :size="15" /><span>{{ archaeology.notice }}</span><button @click="closeMessage('notice')">关闭</button>
    </div>
    <div v-if="archaeology.catalog?.recovery.length" class="archaeology-message warning">
      <CircleAlert :size="15" />
      <span>发现 {{ archaeology.catalog.recovery.length }} 项可恢复的导入事务。重新导入同一识别名时会优先保护上一次稳定版本。</span>
    </div>

    <section v-if="workbench" class="archaeology-shell">
      <header class="archaeology-instrument">
        <div class="archaeology-instrument-title">
          <span class="archaeology-instrument-seal"><ScanSearch :size="20" /></span>
          <span><small>{{ workbench.mode.label }}</small><strong>{{ workbench.title }}</strong></span>
        </div>
        <p>{{ modeIntent }}</p>
        <div class="archaeology-summary">
          <span><strong>{{ workbench.sources.length }}</strong><small>来源</small></span>
          <span><strong>{{ workbench.segmentation.chunk_count }}</strong><small>分析块</small></span>
          <span><strong>{{ workbench.evidence.reference_count }}</strong><small>证据引用</small></span>
          <span :data-alert="workbench.conflicts.unresolved_count > 0"><strong>{{ workbench.conflicts.unresolved_count }}</strong><small>未决冲突</small></span>
          <span class="archaeology-progress-dial" :style="{ '--progress': `${progress * 3.6}deg` }"><strong>{{ progress }}%</strong><small>整理进度</small></span>
        </div>
      </header>

      <ArchaeologyJourney :stages="workbench.journey" />
      <ArchaeologyExtractionConsole
        :state="workbench.status"
        :job="archaeology.job"
        :events="archaeology.events"
        :busy="archaeology.workerBusy"
        :stream-error="archaeology.streamError"
        @run="archaeology.runNextTask"
        @approve="archaeology.approveWriteback"
        @reject="archaeology.rejectWriteback"
        @retry="archaeology.retry"
        @stop="archaeology.stop"
      />

      <div class="archaeology-workbench">
        <aside class="archaeology-import-rail">
          <header><span>导入作品</span><small>{{ archaeology.imports.length }}</small></header>
          <div class="archaeology-import-list">
            <button
              v-for="item in archaeology.imports"
              :key="item.work_id"
              :class="{ active: item.work_id === archaeology.selectedWorkId }"
              @click="archaeology.selectWork(item.work_id)"
            >
              <span class="archaeology-work-mark"><FileArchive :size="15" /></span>
              <span><strong>{{ item.title }}</strong><small>{{ item.mode.label }} · {{ item.chunk_count }} 块</small></span>
              <i :data-state="item.status.status">{{ item.status.status === "ready" ? "完成" : "进行中" }}</i>
            </button>
          </div>
          <button class="archaeology-import-another" @click="importOpen = true"><Plus :size="13" />再导入一部作品</button>
        </aside>

        <main class="archaeology-evidence-stage">
          <nav class="archaeology-pane-tabs" aria-label="考古结果视图">
            <button
              v-for="pane in panes"
              :key="pane.id"
              :class="{ active: activePane === pane.id }"
              @click="activePane = pane.id"
            >
              <component :is="pane.icon" :size="14" />{{ pane.label }}
              <i v-if="pane.id === 'conflicts' && workbench.conflicts.unresolved_count">{{ workbench.conflicts.unresolved_count }}</i>
            </button>
          </nav>
          <Transition name="archaeology-pane" mode="out-in">
            <ReconstructionPreview v-if="activePane === 'reconstruction'" :reconstruction="workbench.reconstruction" />
            <EntityResolutionBoard v-else-if="activePane === 'entities'" :entities="workbench.entities" />
            <ConflictWorkbench v-else-if="activePane === 'conflicts'" :conflicts="workbench.conflicts" />
            <SegmentationTimeline v-else :sources="workbench.sources" :segmentation="workbench.segmentation" />
          </Transition>
        </main>

        <aside class="archaeology-right-rail">
          <PromotionQueue :queue="workbench.promotion_queue" :analysis-only="analysisOnly" />
          <section class="archaeology-evidence-integrity">
            <header><span><ShieldCheck :size="14" />证据完整性</span></header>
            <div>
              <strong>{{ workbench.evidence.reference_count }}</strong>
              <small>条候选引用可回到来源范围</small>
            </div>
            <p>身份、冲突和候选资产只显示结果摘要；原始证据仍由正式项目保存和校验。</p>
          </section>
        </aside>
      </div>
    </section>

    <section v-else class="archaeology-empty">
      <span><FileArchive :size="30" /></span>
      <strong>{{ archaeology.busy ? "正在读取已有作品" : "还没有导入作品" }}</strong>
      <p>{{ archaeology.busy ? "正在核对来源、证据和正式任务状态。" : "导入你有权使用的 TXT、Markdown 或 DOCX，ArcVellum 会先保全原文，再逐层恢复人物、世界与情节候选。" }}</p>
      <button v-if="!archaeology.busy" class="archaeology-primary" @click="importOpen = true"><Plus :size="15" />导入第一部作品</button>
    </section>

    <SourceImportPanel
      :open="importOpen"
      :options="archaeology.options"
      :busy="archaeology.importing"
      @close="importOpen = false"
      @import="importSource"
    />
  </div>
</template>
