<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  Archive,
  BookOpenText,
  CheckCheck,
  Compass,
  Database,
  FilePlus2,
  RefreshCw,
  RotateCcw,
  Save,
  SearchCheck,
  ShieldAlert,
  Sparkles,
  Trash2,
} from "lucide-vue-next";
import AssetEditorPane from "./components/AssetEditorPane.vue";
import AssetCreationPanel from "./components/AssetCreationPanel.vue";
import AssetImpactPanel from "./components/AssetImpactPanel.vue";
import AssetTabs from "./components/AssetTabs.vue";
import AssetTree from "./components/AssetTree.vue";
import CandidatePromotionPanel from "./components/CandidatePromotionPanel.vue";
import RecycleBinPanel from "./components/RecycleBinPanel.vue";
import RevisionTimeline from "./components/RevisionTimeline.vue";
import { useArchiveStore } from "./stores/archive";
import { useAppStore } from "@/stores/app";
import { useHumanChoicesStore } from "@/stores/humanChoices";
import GuidedTour from "@/features/onboarding/components/GuidedTour.vue";
import {
  hasCompletedTour,
  markTourCompleted,
} from "@/features/onboarding/services/tourState";
import type { GuidedTourStep } from "@/features/onboarding/types";
import type { RecycleEntry } from "./types";
import type { ArchiveCreationPayload } from "./types";
import "./archive.css";

const app = useAppStore();
const archive = useArchiveStore();
const choices = useHumanChoicesStore();
const mode = ref<"formal" | "candidate" | "recycle">("formal");
const queryText = ref("");
const editorMode = ref<"structure" | "source">("structure");
const editReason = ref("");
const ownerWaiver = ref(false);
const archiveReason = ref("");
const restoreReason = ref("");
const showCreation = ref(false);
const showTour = ref(false);
const ARCHIVE_TOUR_VERSION = 1;

const activeId = computed(() =>
  archive.selectedAsset?.asset_id || archive.selectedCandidate?.candidate_id || "",
);
const candidateChoice = computed(() => {
  const id = archive.selectedCandidate?.candidate_id;
  return choices.choices.find((choice) => {
    const target = choice.target && typeof choice.target === "object"
      ? choice.target as Record<string, unknown>
      : {};
    return choice.decision_type === "asset_approval" && target.target_id === id;
  }) || null;
});
const tourSteps = computed<GuidedTourStep[]>(() => {
  const formalCount = archive.assetGroups.reduce(
    (sum, group) => sum + group.items.length,
    0,
  );
  return [
    {
      targetId: "archive-modes",
      eyebrow: "档案的三种状态",
      title: "先分清正式、候选与回收站",
      body: `当前有 ${formalCount} 份正式资料、${archive.candidates.length} 个候选。候选不会因为出现在这里就自动成为作品事实。`,
    },
    {
      targetId: "archive-tree",
      eyebrow: "作品资产",
      title: "按作品概念找资料，不必翻项目文件",
      body: "人物、场景、世界规则与叙事账本都以稳定身份列在这里。筛选只改变当前列表，不改变作品内容。",
    },
    ...(archive.selectedAsset ? [
      {
        targetId: "archive-editor",
        eyebrow: "受控校勘",
        title: `正在编辑“${archive.selectedAsset.title}”`,
        body: "默认结构化编辑只开放 Registry 允许的字段；专家源文本用于修复复杂格式。两种模式共享同一份未保存草稿。",
      },
      {
        targetId: "archive-author-transaction",
        eyebrow: archive.dirty ? "有未保存修改" : "作者权威事务",
        title: archive.dirty ? "先检查影响，再保存版本" : "修改不会直接越过工程保护",
        body: "保存前必须说明原因、检查结构与影响，并确认作者决定。Schema、引用、版本冲突和原子写入不能被豁免。",
      },
    ] : []),
    {
      targetId: "archive-candidates",
      eyebrow: "候选进入正式作品",
      title: "晋升仍由 Engine Gate 决定",
      body: archive.candidates.length
        ? `当前 ${archive.candidates.length} 个候选会显示独立审查、作者决定和晋升证据。`
        : "候选出现后会在这里显示审查、作者决定和晋升证据；档案界面不会伪造通过状态。",
    },
  ];
});

onMounted(async () => {
  try {
    await archive.loadWorkspace();
    const first = archive.assetGroups.flatMap((group) => group.items)[0];
    if (first) {
      await archive.openAsset(first.asset_id);
      if (!archive.structuredDocument) editorMode.value = "source";
    }
    showTour.value = !hasCompletedTour("archive", ARCHIVE_TOUR_VERSION);
  } catch {
    // The Archive store already exposes a user-facing failure message.
  }
  void choices.load(app.currentProjectPath).catch((cause) => {
    choices.error = actionMessage(cause, "候选审批信息暂时没有载入，不影响正式档案工作。");
  });
});

function replayTour(): void {
  showTour.value = true;
}

function closeTour(): void {
  showTour.value = false;
  markTourCompleted("archive", ARCHIVE_TOUR_VERSION);
}

async function selectTab(id: string, kind: "asset" | "candidate"): Promise<void> {
  try {
    mode.value = kind === "candidate" ? "candidate" : "formal";
    if (kind === "candidate") await archive.openCandidate(id);
    else {
      await archive.openAsset(id);
      await ensureStructuredEditor();
    }
  } catch {
    if (archive.selectedAsset && !archive.structuredDocument) editorMode.value = "source";
    // Store state preserves the actionable error.
  }
}

async function openAsset(assetId: string): Promise<void> {
  mode.value = "formal";
  try {
    await archive.openAsset(assetId);
    await ensureStructuredEditor();
  } catch {
    if (archive.selectedAsset && !archive.structuredDocument) editorMode.value = "source";
    // Store state preserves the actionable error.
  }
}

async function openCandidate(candidateId: string): Promise<void> {
  mode.value = "candidate";
  try {
    await archive.openCandidate(candidateId);
  } catch {
    // Store state preserves the actionable error.
  }
}

async function reloadWorkspace(): Promise<void> {
  try {
    await archive.loadWorkspace();
  } catch {
    // Store state preserves the actionable error.
  }
}

async function runPreview(): Promise<void> {
  try {
    await archive.previewEdit();
  } catch {
    // Store state preserves the actionable error.
  }
}

async function changeEditorMode(value: "structure" | "source"): Promise<void> {
  if (value === "structure") {
    try {
      await ensureStructuredEditor();
    } catch {
      editorMode.value = "source";
      // Store state preserves the actionable error.
      return;
    }
  }
  editorMode.value = value;
}

async function applyStructuredFields(fields: Record<string, unknown>): Promise<void> {
  try {
    await archive.applyStructuredFields(fields);
  } catch {
    // Store state preserves the actionable error.
  }
}

async function closeTab(id: string, kind: "asset" | "candidate"): Promise<void> {
  try {
    await archive.closeTab(id, kind);
  } catch (cause) {
    archive.error = actionMessage(cause, "标签没有关闭。");
  }
}

async function discardDraft(): Promise<void> {
  try {
    await archive.discardCurrentDraft();
  } catch (cause) {
    archive.error = actionMessage(cause, "当前草稿没有恢复。");
  }
}

async function ensureStructuredEditor(): Promise<void> {
  if (archive.selectedAsset && !archive.structuredDocument) {
    await archive.reloadStructuredDocument();
  }
}

async function saveOwnerVersion(): Promise<void> {
  try {
    await archive.commitEdit(editReason.value, ownerWaiver.value);
    editReason.value = "";
    ownerWaiver.value = false;
  } catch {
    // Store state preserves the actionable error.
  }
}

async function moveToRecycleBin(): Promise<void> {
  if (!archiveReason.value.trim()) return;
  try {
    await archive.archiveAsset(archiveReason.value);
    archiveReason.value = "";
  } catch (cause) {
    archive.error = actionMessage(cause, "资料没有移入回收站。");
  }
}

async function decideCandidate(option: Record<string, unknown>): Promise<void> {
  if (!candidateChoice.value) return;
  choices.open(candidateChoice.value);
  try {
    await choices.submit(app.currentProjectPath, option);
    await Promise.all([archive.refreshCandidate(), choices.load(app.currentProjectPath)]);
  } catch (cause) {
    archive.error = actionMessage(cause, "作者决定没有写入正式流程。");
  }
}

async function promoteCandidate(): Promise<void> {
  try {
    const job = await archive.promoteCandidate();
    void monitorPromotion(String(job.job_id || ""));
  } catch (cause) {
    archive.error = actionMessage(cause, "候选没有进入正式晋升任务。");
  }
}

async function monitorPromotion(jobId: string): Promise<void> {
  if (!jobId) return;
  try {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
      const result = await import("@/services/api").then(({ api }) => api<Record<string, unknown>>(`/worker/jobs/${jobId}`));
      archive.promotionJob = result;
      if (!["queued", "running", "stopping"].includes(String(result.status || ""))) {
        await archive.refreshCandidate();
        return;
      }
    }
  } catch (cause) {
    archive.error = actionMessage(cause, "晋升任务状态暂时无法刷新。");
  }
}

async function restore(item: RecycleEntry): Promise<void> {
  try {
    await archive.restoreEntry(item, restoreReason.value);
  } catch (cause) {
    archive.error = actionMessage(cause, "资料没有恢复到正式档案。");
  }
}

async function previewCreation(payload: ArchiveCreationPayload): Promise<void> {
  try {
    await archive.previewCreation(payload);
  } catch {
    // Store state preserves the actionable error.
  }
}

async function createAsset(payload: ArchiveCreationPayload): Promise<void> {
  try {
    await archive.createAsset(payload);
    showCreation.value = false;
    mode.value = "formal";
  } catch {
    // Store state preserves the actionable error.
  }
}

function actionMessage(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}
</script>

<template>
  <div class="archive-ide-view">
    <header class="archive-ide-header">
      <div>
        <span>作品资产工作面</span>
        <h1>Narrative Archive</h1>
        <p>作者修改、候选晋升与版本证据在同一条受控链路中完成。</p>
      </div>
      <div class="archive-header-actions">
        <RouterLink to="/library"><BookOpenText :size="15" />回到亲用户浏览</RouterLink>
        <button title="查看本页引导" @click="replayTour"><Compass :size="15" /></button>
        <button :disabled="archive.busy" title="重新读取作品资产" @click="reloadWorkspace"><RefreshCw :size="15" /></button>
      </div>
    </header>

    <nav class="archive-mode-bar" data-tour-id="archive-modes" aria-label="档案工作区">
      <button :class="{ active: mode === 'formal' }" @click="mode = 'formal'"><Database :size="15" />正式资产<span>{{ archive.assetGroups.reduce((sum, group) => sum + group.items.length, 0) }}</span></button>
      <button data-tour-id="archive-candidates" :class="{ active: mode === 'candidate' }" @click="mode = 'candidate'"><Sparkles :size="15" />候选与晋升<span>{{ archive.candidates.length }}</span></button>
      <button :class="{ active: mode === 'recycle' }" @click="mode = 'recycle'"><Archive :size="15" />回收站<span>{{ archive.recycleEntries.length }}</span></button>
      <i></i>
      <button class="archive-create-trigger" @click="showCreation = true"><FilePlus2 :size="15" />新建资料</button>
      <small v-if="archive.busy">正在核对项目文件…</small>
      <small v-else>所有正式写入都有版本与回执</small>
    </nav>

    <div v-if="archive.error || archive.notice" class="archive-feedback" :class="{ error: archive.error }">
      <ShieldAlert v-if="archive.error" :size="15" />
      <CheckCheck v-else :size="15" />
      <span>{{ archive.error || archive.notice }}</span>
      <button @click="archive.clearMessages">关闭</button>
    </div>

    <main class="archive-ide-grid">
      <AssetTree
        data-tour-id="archive-tree"
        :groups="archive.assetGroups"
        :candidates="archive.candidates"
        :recycle-entries="archive.recycleEntries"
        :mode="mode"
        :query="queryText"
        :selected-id="activeId"
        @update-query="queryText = $event"
        @select-asset="openAsset"
        @select-candidate="openCandidate"
      />

      <section v-if="mode === 'formal'" class="archive-workspace">
        <AssetTabs
          :tabs="archive.openTabs"
          :active-id="activeId"
          :dirty-ids="archive.dirtyAssetIds"
          @select="selectTab"
          @close="closeTab"
        />
        <AssetEditorPane
          v-if="archive.selectedAsset"
          data-tour-id="archive-editor"
          :asset="archive.selectedAsset"
          :model-value="archive.draft"
          :mode="editorMode"
          :structure="archive.structuredDocument"
          :busy="archive.busy"
          @update:model-value="archive.updateDraft"
          @update:mode="changeEditorMode"
          @apply-structure="applyStructuredFields"
        />
        <div v-else class="archive-workspace-empty"><Database :size="28" /><strong>选择一份正式资料</strong><p>人物、场景和世界规则会在这里以作者版本打开。</p></div>
      </section>

      <aside v-if="mode === 'formal'" class="archive-revision-spine" data-tour-id="archive-author-transaction">
        <section class="archive-save-panel">
          <header><Save :size="15" /><strong>作者事务</strong></header>
          <label><span>修改原因</span><textarea v-model="editReason" placeholder="说明这次修改要解决什么问题"></textarea></label>
          <label class="archive-owner-check"><input v-model="ownerWaiver" type="checkbox" /><span>以作者决定为准，保留审计并重新检查受影响链路</span></label>
          <div>
            <button :disabled="!archive.dirty || archive.busy" title="放弃当前标签的未保存修改" @click="discardDraft"><RotateCcw :size="14" />放弃草稿</button>
            <button :disabled="!archive.dirty || archive.busy" @click="runPreview"><SearchCheck :size="14" />检查变更</button>
            <button class="primary" :disabled="!archive.dirty || !editReason.trim() || !ownerWaiver || archive.validation?.valid !== true || archive.busy" @click="saveOwnerVersion"><Save :size="14" />保存版本</button>
          </div>
        </section>
        <AssetImpactPanel :validation="archive.validation" :impact="archive.impact" />
        <RevisionTimeline :history="archive.history" />
        <section v-if="archive.selectedAsset?.supports_archive" class="archive-danger-panel">
          <header><Trash2 :size="14" /><strong>归档资料</strong></header>
          <input v-model="archiveReason" placeholder="说明归档原因" />
          <button :disabled="!archiveReason.trim() || archive.busy" @click="moveToRecycleBin">移入回收站</button>
        </section>
      </aside>

      <CandidatePromotionPanel
        v-if="mode === 'candidate' && archive.selectedCandidate"
        class="archive-wide-stage"
        :candidate="archive.selectedCandidate"
        :choice="candidateChoice"
        :decision-error="choices.error"
        :busy="archive.busy"
        :job="archive.promotionJob"
        @decide="decideCandidate"
        @promote="promoteCandidate"
        @refresh="archive.refreshCandidate"
      />
      <div v-else-if="mode === 'candidate'" class="archive-wide-stage archive-workspace-empty"><Sparkles :size="28" /><strong>选择一个候选资产</strong><p>独立审查、作者批准和正式晋升会按顺序显示。</p></div>

      <RecycleBinPanel
        v-if="mode === 'recycle'"
        class="archive-wide-stage"
        :items="archive.recycleEntries"
        :busy="archive.busy"
        :reason="restoreReason"
        @update:reason="restoreReason = $event"
        @restore="restore"
      />
    </main>

    <AssetCreationPanel
      v-if="showCreation"
      :options="archive.creationOptions"
      :preview="archive.creationPreview"
      :busy="archive.busy"
      @close="showCreation = false"
      @reset-preview="archive.resetCreationPreview"
      @preview="previewCreation"
      @create="createAsset"
    />
    <GuidedTour
      :active="showTour"
      :steps="tourSteps"
      complete-label="开始管理档案"
      @complete="closeTour"
      @dismiss="closeTour"
    />
  </div>
</template>
