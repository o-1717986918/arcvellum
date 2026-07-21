<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import {
  BookOpenText,
  Boxes,
  ChevronDown,
  CircleHelp,
  Cog,
  FolderKanban,
  LibraryBig,
  PackageCheck,
  Info,
  Orbit,
  RefreshCw,
  Settings2,
  SlidersHorizontal,
} from "lucide-vue-next";
import StartupScene from "@/components/StartupScene.vue";
import AdvisorDock from "@/components/AdvisorDock.vue";
import OnboardingTour from "@/components/OnboardingTour.vue";
import { normalizeOrreryTheme } from "@/services/orreryPreferences";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const showStartup = ref(true);
const startupMinimumElapsed = ref(false);
const startupVisualSkippable = ref(false);
const showOnboarding = ref(false);
document.documentElement.dataset.arcvellumTheme = normalizeOrreryTheme(window.localStorage.getItem("arcvellum.visualTheme"));

const nav = [
  { to: "/projects", label: "作品", icon: FolderKanban, needsProject: false },
  { to: "/overview", label: "创作总控", icon: Boxes, needsProject: true },
  { to: "/reader", label: "阅读", icon: BookOpenText, needsProject: true },
  { to: "/library", label: "作品档案", icon: LibraryBig, needsProject: true },
  { to: "/quality", label: "创作规则", icon: SlidersHorizontal, needsProject: true },
  { to: "/delivery", label: "交付", icon: PackageCheck, needsProject: true },
  { to: "/settings", label: "设置", icon: Settings2, needsProject: false },
];

const statusLabel = computed(() => {
  const phase = store.bootstrap?.phase;
  if (phase === "blocked") return "需要处理";
  if (phase === "degraded") return "可用，部分连接离线";
  if (phase === "starting") return "正在准备";
  return "运行正常";
});

async function enterImmersiveOrrery(): Promise<void> {
  if (!store.hasProject) {
    await router.push("/projects");
    return;
  }
  window.localStorage.setItem("arcvellum.orreryMode", "immersive");
  await router.push("/overview");
  window.dispatchEvent(new CustomEvent("arcvellum:orrery-mode", { detail: "immersive" }));
}

onMounted(async () => {
  window.addEventListener("arcvellum:onboarding", openOnboarding);
  const returning = window.localStorage.getItem("arcvellum.startup-seen") === "1";
  window.setTimeout(() => (startupVisualSkippable.value = true), 600);
  window.setTimeout(() => (startupMinimumElapsed.value = true), returning ? 560 : 1950);
  await store.initialize();
  if (store.currentProjectPath) await store.refreshWorkspace();
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
    if (!path && ["overview", "reader", "library", "delivery"].includes(String(route.name))) void router.push("/projects");
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
  store.stopProjectStreams();
  window.removeEventListener("arcvellum:onboarding", openOnboarding);
});
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

  <div class="app-shell" :class="{ 'startup-obscured': showStartup, 'orrery-mode': route.name === 'overview' }">
    <aside class="sidebar">
      <div class="brand-lockup" aria-label="ArcVellum">
        <div class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
        <div>
          <strong>ArcVellum</strong>
          <small>长篇创作观测台</small>
        </div>
      </div>

      <div class="project-switcher" data-tour="project">
        <label for="project-switcher">当前作品</label>
        <div class="select-wrap">
          <BookOpenText :size="16" aria-hidden="true" />
          <select
            id="project-switcher"
            :value="store.currentProjectPath"
            @change="store.setCurrentProject(($event.target as HTMLSelectElement).value)"
          >
            <option value="">选择一部作品</option>
            <option v-for="project in store.projects" :key="project.path" :value="project.path">
              {{ project.title }}
            </option>
          </select>
          <ChevronDown :size="15" aria-hidden="true" />
        </div>
        <p>{{ store.currentProject?.premise || "从一个创作方向开始。" }}</p>
      </div>

      <button class="sidebar-orrery-entry" data-tour="orrery" :disabled="!store.hasProject" title="进入叙事星仪全景工作台" @click="enterImmersiveOrrery">
        <span class="sidebar-orrery-orbit"><Orbit :size="19" /></span>
        <span class="sidebar-orrery-label"><strong>叙事星仪</strong><small>沉浸全景</small></span>
      </button>

      <nav class="main-nav" data-tour="navigation" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.needsProject && !store.hasProject ? '/projects' : item.to"
          :aria-disabled="item.needsProject && !store.hasProject"
          :title="item.label"
        >
          <component :is="item.icon" :size="18" stroke-width="1.8" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="health-line" :data-state="store.bootstrap?.phase || 'starting'">
          <span class="status-dot"></span>
          <div><strong>{{ statusLabel }}</strong><small>本地工作台</small></div>
          <button class="icon-button" title="重新读取状态" @click="store.initialize"><RefreshCw :size="16" /></button>
        </div>
        <div class="sidebar-meta-links">
          <RouterLink class="quiet-link" data-tour="help" to="/help" title="使用帮助"><CircleHelp :size="16" /><span>使用帮助</span></RouterLink>
          <RouterLink class="quiet-link" to="/details" title="作品与应用详情"><Info :size="16" /><span>详情</span></RouterLink>
        </div>
      </div>
    </aside>

    <main class="workspace">
      <header v-if="route.name !== 'overview'" class="workspace-header">
        <div>
          <span class="context-label">{{ String(route.meta.label || "ArcVellum") }}</span>
          <strong>{{ store.currentProject?.title || "建立你的第一部作品" }}</strong>
        </div>
        <div class="header-actions">
          <select v-if="store.projects.length" class="header-project-select" :value="store.currentProjectPath" aria-label="切换当前作品" @change="store.setCurrentProject(($event.target as HTMLSelectElement).value)">
            <option v-for="project in store.projects" :key="project.path" :value="project.path">{{ project.title }}</option>
          </select>
          <span v-if="store.notice" class="inline-notice">{{ store.notice }}</span>
          <RouterLink class="icon-button" to="/settings" title="应用设置"><Cog :size="18" /></RouterLink>
        </div>
      </header>
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
    <AdvisorDock />
    <OnboardingTour :active="showOnboarding && !showStartup" :has-project="store.hasProject" @complete="closeOnboarding" @dismiss="closeOnboarding" />
  </div>
</template>
