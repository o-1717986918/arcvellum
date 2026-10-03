<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { useAppStore } from "@/stores/app";
import CharacterChatPanel from "./CharacterChatPanel.vue";
const app = useAppStore();
const route = useRoute();
const router = useRouter();
</script>
<template>
  <CharacterChatPanel :key="app.currentProjectPath" :project-root="app.currentProjectPath" :initial-target="String(route.query.target || '')"
    @close="router.push('/archive')" />
</template>
