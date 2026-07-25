<script setup lang="ts">
import {
  BookMarked,
  CheckCheck,
  Fingerprint,
  FlaskConical,
  PackageCheck,
  Scale,
} from "lucide-vue-next";
import type { Component } from "vue";
import type { StyleJourneyStage } from "../types";

defineProps<{ stages: StyleJourneyStage[] }>();

const icons: Record<string, Component> = {
  sources: BookMarked,
  profiles: Fingerprint,
  evaluation: FlaskConical,
  review: Scale,
  versions: PackageCheck,
  mount: CheckCheck,
};
</script>

<template>
  <ol class="style-journey" aria-label="文风形成进度">
    <li
      v-for="stage in stages"
      :key="stage.id"
      :data-state="stage.status"
    >
      <span class="style-journey-node">
        <component :is="icons[stage.id] || Fingerprint" :size="15" aria-hidden="true" />
      </span>
      <span>
        <strong>{{ stage.label }}</strong>
        <small>{{ stage.count ? `${stage.count} 项已就绪` : "等待建立" }}</small>
      </span>
    </li>
  </ol>
</template>
