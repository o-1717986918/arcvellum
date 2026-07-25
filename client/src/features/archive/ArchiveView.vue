<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  Archive,
  BookOpenText,
  CheckCheck,
  Database,
  RefreshCw,
  Save,
  SearchCheck,
  ShieldAlert,
  Sparkles,
  Trash2,
} from "lucide-vue-next";
import AssetEditorPane from "./components/AssetEditorPane.vue";
import AssetImpactPanel from "./components/AssetImpactPanel.vue";
import AssetTabs from "./components/AssetTabs.vue";
import AssetTree from "./components/AssetTree.vue";
import CandidatePromotionPanel from "./components/CandidatePromotionPanel.vue";
import RecycleBinPanel from "./components/RecycleBinPanel.vue";
import RevisionTimeline from "./components/RevisionTimeline.vue";
import { useArchiveStore } from "./stores/archive";
import { useAppStore } from "@/stores/app";
import { useHumanChoicesStore } from "@/stores/humanChoices";
import type { RecycleEntry } from "./types";
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

onMounted(async () => {
  try {
    await archive.loadWorkspace();
    const first = archive.assetGroups.flatMap((group) => group.items)[0];
    if (first) await archive.openAsset(first.asset_id);
  } catch {
    // The Archive store already exposes a user-facing failure message.
  }
  void choices.load(app.currentProjectPath).catch((cause) => {
    choices.error = actionMessage(cause, "候选审批信息暂时没有载入，不影响正式档案工作。");
  });
});

async function selectTab(id: string, kind: "asset" | "candidate"): Promise<void> {
  try {
    mode.value = kind === "candidate" ? "candidate" : "formal";
    if (kind === "candidate") await archive.openCandidate(id);
    else await archive.openAsset(id);
  } catch {
    // Store state preserves the actionable error.
  }
}

async function openAsset(assetId: string): Promise<void> {
  mode.value = "formal";
  try {
    await archive.openAsset(assetId);
  } catch {
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
        <button :disabled="archive.busy" title="重新读取作品资产" @click="reloadWorkspace"><RefreshCw :size="15" /></button>
      </div>
    </header>

    <nav class="archive-mode-bar" aria-label="档案工作区">
      <button :class="{ active: mode === 'formal' }" @click="mode = 'formal'"><Database :size="15" />正式资产<span>{{ archive.assetGroups.reduce((sum, group) => sum + group.items.length, 0) }}</span></button>
      <button :class="{ active: mode === 'candidate' }" @click="mode = 'candidate'"><Sparkles :size="15" />候选与晋升<span>{{ archive.candidates.length }}</span></button>
      <button :class="{ active: mode === 'recycle' }" @click="mode = 'recycle'"><Archive :size="15" />回收站<span>{{ archive.recycleEntries.length }}</span></button>
      <i></i>
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
          :dirty="archive.dirty"
          @select="selectTab"
          @close="archive.closeTab"
        />
        <AssetEditorPane
          v-if="archive.selectedAsset"
          :asset="archive.selectedAsset"
          :model-value="archive.draft"
          :mode="editorMode"
          @update:model-value="archive.updateDraft"
          @update:mode="editorMode = $event"
        />
        <div v-else class="archive-workspace-empty"><Database :size="28" /><strong>选择一份正式资料</strong><p>人物、场景和世界规则会在这里以作者版本打开。</p></div>
      </section>

      <aside v-if="mode === 'formal'" class="archive-revision-spine">
        <section class="archive-save-panel">
          <header><Save :size="15" /><strong>作者事务</strong></header>
          <label><span>修改原因</span><textarea v-model="editReason" placeholder="说明这次修改要解决什么问题"></textarea></label>
          <label class="archive-owner-check"><input v-model="ownerWaiver" type="checkbox" /><span>以作者决定为准，保留审计并重新检查受影响链路</span></label>
          <div>
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
  </div>
</template>
