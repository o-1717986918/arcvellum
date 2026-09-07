<script setup lang="ts">
import { computed, onErrorCaptured, ref, watch } from "vue";
import { RefreshCw, TriangleAlert } from "lucide-vue-next";
import { creativeWorkspaceRegistry } from "@/workspaces/creativeWorkspaceRegistry";
import type { SpatialWindowKind } from "@/types/spatialWindows";

const props = defineProps<{ kind: SpatialWindowKind }>();

const descriptor = computed(() => creativeWorkspaceRegistry.get(props.kind));
const workspace = computed(() => descriptor.value?.component);
const loadError = ref("");

watch(() => props.kind, () => { loadError.value = ""; });
onErrorCaptured((cause) => {
  loadError.value = cause instanceof Error ? cause.message : String(cause);
  return false;
});

function reloadWorkspace(): void {
  window.location.reload();
}
</script>

<template>
  <section class="creative-workspace-host" :data-workspace="descriptor?.workspaceId">
    <div v-if="loadError" class="creative-workspace-error" role="alert">
      <span><TriangleAlert :size="20" /></span>
      <strong>工作台资源需要重新连接</strong>
      <p>页面资源可能刚刚更新。重新载入后会保留当前作品，并从原位置继续。</p>
      <button class="primary-button" @click="reloadWorkspace"><RefreshCw :size="15" />重新载入</button>
      <details><summary>诊断信息</summary><code>{{ loadError }}</code></details>
    </div>
    <Suspense v-else>
      <component :is="workspace" v-if="workspace" />
      <template #fallback><div class="creative-workspace-loading"><i></i><strong>正在展开工作台</strong></div></template>
    </Suspense>
  </section>
</template>
