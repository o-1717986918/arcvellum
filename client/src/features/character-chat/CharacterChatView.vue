<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { useAppStore } from "@/stores/app";
import CharacterChatPanel from "./CharacterChatPanel.vue";
const app = useAppStore();
const route = useRoute();
const router = useRouter();

function close(): void {
  const query = { ...route.query };
  if (query.characterReturn === "archive") query.workspace = "archive";
  else delete query.workspace;
  delete query.characterReturn;
  delete query.target;
  void router.replace({ name: "project-agent", query });
}
</script>
<template>
  <div class="character-chat-page">
    <CharacterChatPanel v-if="route.name === 'project-agent' && route.query.workspace === 'character-chat'"
      :key="app.currentProjectPath" :project-root="app.currentProjectPath" :initial-target="String(route.query.target || '')"
      @close="close" />
  </div>
</template>
