<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import StartupScene from "@/components/StartupScene.vue";
import AdvisorDock from "@/features/advisor/components/AdvisorDock.vue";
import OnboardingTour from "@/components/OnboardingTour.vue";
import { projectsClient } from "@/features/projects/services/projectsClient";
import { workflowClient } from "@/features/workflow/services/workflowClient";
import { applyOrreryExperience } from "@/services/orreryPreferences";
import { createWorkspaceCommandHandler } from "@/services/workspaceCommandHandler";
import { workspaceCommandBus } from "@/services/workspaceCommands";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const showStartup = ref(true);
const startupMinimumElapsed = ref(false);
const startupVisualSkippable = ref(false);
const showOnboarding = ref(false);
let removeWorkspaceCommandHandler: (() => void) | null = null;
applyOrreryExperience({});

onMounted(async () => {
  removeWorkspaceCommandHandler = workspaceCommandBus.install(createWorkspaceCommandHandler({
    projectRoot: () => store.currentProjectPath,
    navigate: async (view) => { await router.push(`/${view}`); },
    recordDirection: (root, message) => projectsClient.addDirection(root, message),
    runRoute: async (root, routeName, runtime) => await workflowClient.runWorker(root, routeName, runtime),
    startAutopilot: async (root, runtime) => await workflowClient.startAutopilot({ project_root: root, runtime }) as unknown as Record<string, unknown>,
    autopilotStatus: async (root) => await workflowClient.autopilotStatus(root),
    pauseAutopilot: (runId, reason) => workflowClient.pauseAutopilot(runId, reason),
    resumeAutopilot: (runId) => workflowClient.resumeAutopilot(runId),
    refresh: () => store.refreshWorkspace(),
  }));
  window.addEventListener("arcvellum:onboarding", openOnboarding);
  window.addEventListener("arcvellum:startup-error", handleStartupError);
  const startupError = window.__ARCVELLUM_STARTUP_ERROR?.message;
  if (startupError) store.reportStartupError(startupError);
  const returning = window.localStorage.getItem("arcvellum.startup-seen") === "1";
  window.setTimeout(() => (startupVisualSkippable.value = true), 600);
  window.setTimeout(() => (startupMinimumElapsed.value = true), returning ? 560 : 1950);
  try {
    await waitForBackendReady();
    await store.initialize();
    if (store.currentProjectPath) await store.refreshWorkspace();
  } catch (cause) {
    store.reportStartupError(cause instanceof Error ? cause.message : "本地创作服务没有成功启动。");
  }
});

watch(
  [() => store.bootstrap?.can_enter_workspace, startupMinimumElapsed],
  ([ready, elapsed]) => {
    if (ready && elapsed) showStartup.value = false;
    if (ready && elapsed) window.localStorage.setItem("arcvellum.startup-seen", "1");
  },
  { immediate: true },
);

watch(showStartup, (visible) => {
  if (!visible && window.localStorage.getItem("arcvellum.onboarding-seen") !== "1") showOnboarding.value = true;
});

watch(
  () => store.currentProjectPath,
  (path) => {
    if (!path && route.name === "overview") void router.push({ name: "project-agent", query: { workspace: "projects" } });
  },
);

function openOnboarding(): void {
  showOnboarding.value = true;
}

function closeOnboarding(): void {
  showOnboarding.value = false;
  window.localStorage.setItem("arcvellum.onboarding-seen", "1");
}

onBeforeUnmount(() => {
  removeWorkspaceCommandHandler?.();
  removeWorkspaceCommandHandler = null;
  store.stopProjectStreams();
  window.removeEventListener("arcvellum:onboarding", openOnboarding);
  window.removeEventListener("arcvellum:startup-error", handleStartupError);
});

function handleStartupError(event: Event): void {
  const detail = (event as CustomEvent<{ message?: string }>).detail;
  store.reportStartupError(detail?.message || "本地创作服务没有成功启动，请重试。");
}

async function waitForBackendReady(): Promise<void> {
  // Browser development uses Vite's local proxy; the packaged desktop client
  // waits for Tauri to inject the nonce-verified loopback endpoint instead.
  if (!window.__LES_API_TOKEN || window.__ARCVELLUM_BACKEND_READY) return;
  await new Promise<void>((resolve, reject) => {
    const onReady = () => {
      cleanup();
      resolve();
    };
    const onFailure = (event: Event) => {
      cleanup();
      const detail = (event as CustomEvent<{ message?: string }>).detail;
      reject(new Error(detail?.message || "本地创作服务没有成功启动。"));
    };
    const cleanup = () => {
      window.removeEventListener("arcvellum:backend-ready", onReady);
      window.removeEventListener("arcvellum:startup-error", onFailure);
    };
    window.addEventListener("arcvellum:backend-ready", onReady, { once: true });
    window.addEventListener("arcvellum:startup-error", onFailure, { once: true });
  });
}
</script>

<template>
  <Transition name="startup-fade">
    <StartupScene
      v-if="showStartup"
      :snapshot="store.bootstrap"
      :error="store.error"
      :visual-skippable="startupVisualSkippable"
      @continue="showStartup = false"
      @retry="store.initialize"
    />
  </Transition>

  <div class="app-shell" :class="{ 'startup-obscured': showStartup, 'orrery-mode': route.name === 'overview', 'agent-stage-mode': route.name === 'project-agent' }">
    <main class="workspace">
      <div v-if="store.error" class="global-message danger" role="alert">
        <span>{{ store.error }}</span>
        <button @click="store.clearMessages">关闭</button>
      </div>
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>
    <AdvisorDock v-if="route.name === 'overview'" />
    <OnboardingTour :active="showOnboarding && !showStartup" :has-project="store.hasProject" @complete="closeOnboarding" @dismiss="closeOnboarding" />
  </div>
</template>
