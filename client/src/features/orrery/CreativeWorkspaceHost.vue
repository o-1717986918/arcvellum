<script setup lang="ts">
import { computed } from "vue";
import { creativeWorkspaceRegistry } from "@/workspaces/creativeWorkspaceRegistry";
import type { SpatialWindowKind } from "@/types/spatialWindows";

const props = defineProps<{ kind: SpatialWindowKind }>();

const descriptor = computed(() => creativeWorkspaceRegistry.get(props.kind));
const workspace = computed(() => descriptor.value?.component);
</script>

<template>
  <section class="creative-workspace-host" :data-workspace="descriptor?.workspaceId">
    <Suspense>
      <component :is="workspace" v-if="workspace" />
      <template #fallback><div class="creative-workspace-loading"><i></i><strong>正在展开工作台</strong></div></template>
    </Suspense>
  </section>
</template>
