<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { Eye, EyeOff, Image, Palette, X } from "lucide-vue-next";
import { useRoute } from "vue-router";
import WorkspaceOrreryHost from "@/components/WorkspaceOrreryHost.vue";
import { workflowClient } from "@/features/workflow/services/workflowClient";
import { readCreativeRuntime } from "@/services/runtimePreference";
import { asList } from "@/services/presentation";
import {
  applyOrreryExperience,
  backgroundForTheme,
  normalizeInstrumentVisibility,
  normalizeOrreryBackground,
  normalizeOrreryTheme,
  type OrreryBackground,
  type OrreryTheme,
} from "@/services/orreryPreferences";
import { loadOrreryBackground } from "@/services/orreryAssets";
import { useAppStore } from "@/stores/app";
import { useHumanChoicesStore } from "@/stores/humanChoices";
import { useSpatialWindowsStore } from "@/stores/spatialWindows";
import type { SpatialWindowKind } from "@/types/spatialWindows";

const store = useAppStore();
const route = useRoute();
const humanChoices = useHumanChoicesStore();
const spatialWindows = useSpatialWindowsStore();
const {
  selectedChoice,
  rationale: choiceRationale,
  busy: choiceBusy,
  completed: choiceCompleted,
  message: choiceMessage,
  error: choiceError,
} = storeToRefs(humanChoices);

const working = ref(false);
const background = ref<OrreryBackground>(normalizeOrreryBackground(localStorage.getItem("arcvellum.orreryBackground")));
const theme = ref<OrreryTheme>(normalizeOrreryTheme(localStorage.getItem("arcvellum.visualTheme")));
const backgroundImage = ref("");
const instrumentsVisible = ref(normalizeInstrumentVisibility(localStorage.getItem("arcvellum.orreryInstruments")));
const heroStyle = computed(() => ({ "--orrery-background-image": backgroundImage.value ? `url("${backgroundImage.value}")` : "none" }));
const dashboard = computed(() => (store.dashboard || null) as Record<string, unknown> | null);
const nextActions = computed(() => asList<Record<string, unknown>>(dashboard.value?.next_actions));
const firstAction = computed(() => nextActions.value[0] || null);
const activeRun = computed(() => {
  const run = store.autopilotStatus?.run || null;
  return run && ["running", "paused", "blocked", "failed"].includes(run.status) ? run : null;
});
const workspaceQueryKinds = new Set<Exclude<SpatialWindowKind, "node">>([
  "progress", "agent", "reader", "decisions", "rules", "health", "delivery",
  "archive", "style", "quality", "strategy", "observatory", "archaeology",
]);

onMounted(async () => {
  localStorage.setItem("arcvellum.orreryMode", "immersive");
  document.documentElement.classList.add("orrery-immersive");
  await store.refreshWorkspace();
  await loadChoices();
  openWorkspaceQuery(route.query.workspace);
});

onBeforeUnmount(() => document.documentElement.classList.remove("orrery-immersive"));

watch(background, (value) => localStorage.setItem("arcvellum.orreryBackground", value));
watch(background, async (value, _previous, onCleanup) => {
  let active = true;
  onCleanup(() => { active = false; });
  backgroundImage.value = "";
  try {
    const source = await loadOrreryBackground(value);
    if (active) backgroundImage.value = source;
  } catch {
    if (active) backgroundImage.value = "";
  }
}, { immediate: true });
watch(theme, (value, previous) => {
  applyOrreryExperience({ theme: value });
  if (previous && previous !== value) background.value = backgroundForTheme(value);
}, { immediate: true });
watch(instrumentsVisible, (value) => localStorage.setItem("arcvellum.orreryInstruments", value ? "visible" : "hidden"));
watch(
  [() => route.query.workspace, () => store.currentProjectPath],
  ([workspace, projectRoot]) => {
    if (!projectRoot) return;
    void store.refreshWorkspace();
    void loadChoices();
    openWorkspaceQuery(workspace);
  },
);

function openWorkspaceQuery(value: unknown): void {
  const kind = String(Array.isArray(value) ? value[0] : value || "");
  if (!workspaceQueryKinds.has(kind as Exclude<SpatialWindowKind, "node">)) return;
  spatialWindows.openInstrument(kind as Exclude<SpatialWindowKind, "node">);
  if (kind === "reader") spatialWindows.setReaderMode("immersive");
  else spatialWindows.setWorkspaceMode("instrument:" + kind, "fullscreen");
}

function openChoice(choice: Record<string, unknown>): void {
  humanChoices.open(choice);
}

function closeChoice(): void {
  humanChoices.close();
}

async function submitChoice(option: Record<string, unknown>): Promise<void> {
  if (!store.currentProjectPath || !selectedChoice.value || choiceBusy.value) return;
  try {
    const result = await humanChoices.submit(store.currentProjectPath, option);
    await store.refreshWorkspace();
    store.notice = choiceMessage.value;
    if (result.consumed) window.setTimeout(() => humanChoices.close(), 480);
  } catch {
    store.error = choiceError.value;
  }
}

async function loadChoices(): Promise<void> {
  if (!store.currentProjectPath) {
    humanChoices.reset();
    return;
  }
  await humanChoices.load(store.currentProjectPath).catch(() => undefined);
}

async function prepareNextTask(): Promise<void> {
  if (!store.currentProjectPath || working.value) return;
  working.value = true;
  try {
    const result = await workflowClient.runWorker(
      store.currentProjectPath,
      String(firstAction.value?.route || "auto"),
      readCreativeRuntime(),
    );
    store.notice = result.job_id ? "下一项创作任务已经启动。" : String(result.message || result.status || "下一项创作任务已经启动。");
    spatialWindows.openInstrument("progress");
    await store.loadDashboard();
  } catch (cause) {
    store.error = cause instanceof Error ? cause.message : "暂时无法启动下一项任务。";
  } finally {
    working.value = false;
  }
}

async function handleActiveRun(): Promise<void> {
  const run = activeRun.value;
  if (!run || working.value) return;
  spatialWindows.openInstrument("progress");
  if (run.status === "running") return;
  if (run.mode === "full_auto") {
    store.notice = "全自动创作需要在推进仪表中确认授权后才能继续。";
    return;
  }
  working.value = true;
  try {
    const result = await workflowClient.resumeAutopilot(run.run_id);
    store.setAutopilotRun(result.run);
    store.notice = "已经从原处继续。";
  } catch (cause) {
    store.error = cause instanceof Error ? cause.message : "暂时无法继续当前任务。";
  } finally {
    working.value = false;
  }
}

function advanceSpatialRun(): void {
  if (activeRun.value) void handleActiveRun();
  else void prepareNextTask();
}
</script>

<template>
  <div class="overview-view is-immersive spatial-active" :class="{ 'instruments-hidden': !instrumentsVisible }" :data-orrery-background="background" data-orrery-engine="spatial">
    <section class="orrery-hero" :style="heroStyle">
      <WorkspaceOrreryHost
        :dashboard="dashboard"
        :immersive="true"
        @advance="advanceSpatialRun"
        @inspect-task="spatialWindows.openInstrument('progress')"
        @open-reader="spatialWindows.openInstrument('reader')"
        @choose="openChoice"
      />

      <div class="orrery-view-tools" aria-label="叙事星仪外观">
        <label title="选择整体观测主题"><Palette :size="15" /><select v-model="theme" aria-label="选择整体观测主题"><option value="moss">苔夜星仪</option><option value="iris">靛紫航图</option><option value="obsidian">黑曜黄铜</option><option value="bookcase">米白书柜</option><option value="modern">冷峻现代</option></select></label>
        <label title="选择星仪背景材质"><Image :size="15" /><select v-model="background" aria-label="选择星仪背景材质"><option value="plain">纯净夜色</option><option value="mineral">绿色矿物星仪</option><option value="iris">靛紫天文制图</option><option value="obsidian">黑曜黄铜机芯</option><option value="bookcase">米白书柜档案</option><option value="modern">冷灰现代观测</option><option value="archive">夜航档案</option><option value="ink">活墨宇宙</option></select></label>
        <button class="orrery-icon" :title="instrumentsVisible ? '暂隐边缘工作台' : '显示边缘工作台'" @click="instrumentsVisible = !instrumentsVisible">
          <EyeOff v-if="instrumentsVisible" :size="16" /><Eye v-else :size="16" />
        </button>
      </div>
    </section>

    <div v-if="selectedChoice" class="choice-dialog-backdrop" @click.self="closeChoice">
      <section class="choice-dialog" role="dialog" aria-modal="true" :aria-label="String(selectedChoice.title || '创作方向选择')">
        <header><div><span class="eyebrow">这一步由你决定</span><h2>{{ selectedChoice.title || "创作方向选择" }}</h2><p>{{ selectedChoice.summary }}</p></div><button class="icon-button" title="关闭" @click="closeChoice"><X :size="16" /></button></header>
        <p v-if="choiceMessage" class="choice-feedback success" role="status">{{ choiceMessage }}</p>
        <p v-if="choiceError" class="choice-feedback error" role="alert">{{ choiceError }}</p>
        <div class="choice-options">
          <button v-for="option in asList<Record<string, unknown>>(selectedChoice.options)" :key="String(option.id)" :disabled="choiceBusy || choiceCompleted" @click="submitChoice(option)">
            <span v-if="String(selectedChoice.recommended || '') === String(option.id)">建议</span>
            <strong>{{ option.label || option.id }}</strong>
            <p>{{ option.summary || "采用这个方向继续推进。" }}</p>
          </button>
        </div>
        <label class="choice-rationale">你还可以补一句理由<textarea v-model.trim="choiceRationale" rows="3" maxlength="2000" placeholder="这会成为后续创作判断的依据。"></textarea></label>
      </section>
    </div>
  </div>
</template>
