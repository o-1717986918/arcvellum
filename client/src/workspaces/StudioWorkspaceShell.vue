<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAppStore } from "@/stores/app";
import vellumOrbits from "@/assets/studio/vellum-orbits.webp";

// Composition lives outside feature modules: neither feature imports the other.
const AgentWorkspace = defineAsyncComponent(() => import("@/features/project-agent/AgentWorkspaceView.vue").then((module) => module.default));
const NarrativeWorkspace = defineAsyncComponent(() => import("@/features/workflow/OverviewView.vue").then((module) => module.default));
const store = useAppStore();
const route = useRoute();
const router = useRouter();
const immersive = computed(() => route.name === "overview");
const agentVisited = ref(!immersive.value);
const shell = ref<HTMLElement | null>(null);
const canShowNarrative = computed(() => Boolean(store.currentProjectPath));

function focusForeground(): void {
  const selector = immersive.value ? ".orrery-return-agent" : ".pa-orrery-entry";
  shell.value?.querySelector<HTMLButtonElement>(selector)?.focus({ preventScroll: true });
}

watch(immersive, async (active) => {
  if (!active) agentVisited.value = true;
  await nextTick();
  focusForeground();
});

function returnOnEscape(event: KeyboardEvent): void {
  if (event.key !== "Escape" || event.defaultPrevented || !immersive.value) return;
  const target = event.target;
  if (target instanceof Element && target.closest("input, textarea, select, [contenteditable=true]")) return;
  const dialogs = document.querySelectorAll<HTMLElement>("[role=dialog], dialog[open]");
  if (Array.from(dialogs).some((item) => !item.closest("[inert]") && item.getClientRects().length)) return;
  event.preventDefault();
  const session = String(route.query.session || "");
  const workspace = String(route.query.workspaceReturn || "");
  void router.push({ name: "project-agent", query: { ...(session ? { session } : {}), ...(workspace ? { workspace } : {}) } });
}
onMounted(() => window.addEventListener("keydown", returnOnEscape));
onBeforeUnmount(() => window.removeEventListener("keydown", returnOnEscape));
</script>

<template>
  <div ref="shell" class="studio-shell" :class="{ 'studio-immersive': immersive, 'studio-has-project': canShowNarrative }">
    <div class="studio-atmosphere" aria-hidden="true">
      <img class="studio-vellum" :src="vellumOrbits" alt="" draggable="false" />
      <span class="studio-light studio-light-a"></span>
      <span class="studio-light studio-light-b"></span>
      <span class="studio-grain"></span>
    </div>
    <div
      v-if="canShowNarrative"
      class="studio-narrative-layer"
      :inert="!immersive"
      :aria-hidden="!immersive"
    >
      <NarrativeWorkspace :active="immersive" @vue:mounted="focusForeground" />
    </div>
    <div
      v-if="agentVisited"
      class="studio-interface-layer"
      :inert="immersive"
      :aria-hidden="immersive"
    >
      <AgentWorkspace @vue:mounted="focusForeground" />
    </div>
  </div>
</template>
