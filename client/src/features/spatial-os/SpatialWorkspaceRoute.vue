<script setup lang="ts">
import { onMounted } from "vue";
import { Orbit } from "lucide-vue-next";
import { useRouter } from "vue-router";
import { useAppStore } from "@/stores/app";
import type { SpatialWindowKind } from "@/types/spatialWindows";

const props = defineProps<{ workspace: Exclude<SpatialWindowKind, "node"> }>();
const router = useRouter();
const app = useAppStore();

onMounted(() => {
  if (!app.currentProjectPath) {
    void router.replace("/projects");
    return;
  }
  void router.replace({ name: "overview", query: { workspace: props.workspace } });
});
</script>

<template>
  <main class="spatial-route-handoff" aria-live="polite">
    <Orbit :size="22" aria-hidden="true" />
    <strong>正在把工作台接回创作星链</strong>
    <span>作品资料、任务和编辑工具会在同一空间内打开。</span>
  </main>
</template>
