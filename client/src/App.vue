<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import {
  Archive,
  BookOpenText,
  Boxes,
  ChevronDown,
  CircleHelp,
  Cog,
  FolderKanban,
  LibraryBig,
  PackageCheck,
  RefreshCw,
  Settings2,
} from "lucide-vue-next";
import StartupScene from "@/components/StartupScene.vue";
import AdvisorDock from "@/components/AdvisorDock.vue";
import { useAppStore } from "@/stores/app";

const store = useAppStore();
const route = useRoute();
const router = useRouter();
const showStartup = ref(true);
const startupMinimumElapsed = ref(false);

const nav = [
  { to: "/projects", label: "作品", icon: FolderKanban, needsProject: false },
  { to: "/overview", label: "创作总控", icon: Boxes, needsProject: true },
  { to: "/reader", label: "阅读", icon: BookOpenText, needsProject: true },
  { to: "/library", label: "作品档案", icon: LibraryBig, needsProject: true },
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

onMounted(async () => {
  window.setTimeout(() => (startupMinimumElapsed.value = true), 850);
  await store.initialize();
  if (store.currentProjectPath) await store.refreshWorkspace();
});

watch(
  [() => store.bootstrap?.can_enter_workspace, startupMinimumElapsed],
  ([ready, elapsed]) => {
    if (ready && elapsed) showStartup.value = false;
  },
  { immediate: true },
);

watch(
  () => store.currentProjectPath,
  (path) => {
    if (!path && ["overview", "reader", "library", "delivery"].includes(String(route.name))) void router.push("/projects");
  },
);

onBeforeUnmount(() => store.stopProjectStreams());
</script>

<template>
  <Transition name="startup-fade">
    <StartupScene
      v-if="showStartup"
      :snapshot="store.bootstrap"
      :error="store.error"
      @continue="showStartup = false"
      @retry="store.initialize"
    />
  </Transition>

  <div class="app-shell" :class="{ 'startup-obscured': showStartup }">
    <aside class="sidebar">
      <div class="brand-lockup" aria-label="ArcVellum">
        <div class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
        <div>
          <strong>ArcVellum</strong>
          <small>长篇创作观测台</small>
        </div>
      </div>

      <div class="project-switcher">
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

      <nav class="main-nav" aria-label="主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.needsProject && !store.hasProject ? '/projects' : item.to"
          :aria-disabled="item.needsProject && !store.hasProject"
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
        <button class="quiet-link"><CircleHelp :size="16" /> 使用帮助</button>
      </div>
    </aside>

    <main class="workspace">
      <header class="workspace-header">
        <div>
          <span class="context-label">{{ String(route.meta.label || "ArcVellum") }}</span>
          <strong>{{ store.currentProject?.title || "建立你的第一部作品" }}</strong>
        </div>
        <div class="header-actions">
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
  </div>
</template>
