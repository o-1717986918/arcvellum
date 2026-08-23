<script setup lang="ts">
import { computed } from "vue";
import type { StageAnchor } from "@/features/orrery/engine/parallaxRenderer";
import type { CreativeProgressionModel, CreativeProgressionStage } from "@/features/orrery/model/creativeProgression";

const props = defineProps<{
  progression: CreativeProgressionModel;
  anchors: Record<string, StageAnchor>;
}>();
const emit = defineEmits<{ focus: [nodeId: string] }>();

const stagePoints = computed(() => {
  const provisional = props.progression.stages.map((stage) => {
  const members = stage.nodeIds.map((nodeId) => props.anchors[nodeId]).filter((anchor): anchor is StageAnchor => Boolean(anchor));
  return {
    stage,
    x: members.length ? members.reduce((sum, anchor) => sum + anchor.x, 0) / members.length : null,
    y: members.length ? members.reduce((sum, anchor) => sum + anchor.y, 0) / members.length : null,
    visible: members.some((anchor) => anchor.visible),
  };
  });
  const available = provisional.filter((point): point is typeof point & { x: number; y: number } => point.x !== null && point.y !== null);
  const centerX = available.length ? available.reduce((sum, point) => sum + point.x, 0) / available.length : 420;
  const centerY = available.length ? available.reduce((sum, point) => sum + point.y, 0) / available.length : 260;
  const spread = Math.max(112, Math.min(184, window.innerWidth * 0.12));
  const middle = (provisional.length - 1) / 2;
  return provisional.map((point, index) => {
    const arcOffset = index - middle;
    return {
      stage: point.stage,
      x: (point.x ?? centerX) + arcOffset * spread,
      y: (point.y ?? centerY) - Math.min(100, 58 + Math.abs(arcOffset) * 8),
      visible: point.visible || point.x === null,
    };
  });
});

const stagePointMap = computed(() => new Map(stagePoints.value.map((point) => [point.stage.id, point])));

function linkPath(sourceId: string, targetId: string): string {
  const source = stagePointMap.value.get(sourceId);
  const target = stagePointMap.value.get(targetId);
  if (!source || !target) return "";
  const bend = Math.max(48, Math.abs(target.x - source.x) * 0.34);
  return `M ${source.x} ${source.y} C ${source.x + bend} ${source.y - 18}, ${target.x - bend} ${target.y + 18}, ${target.x} ${target.y}`;
}

function styleFor(point: { x: number; y: number; visible: boolean }): Record<string, string> {
  return { transform: `translate3d(${point.x}px, ${point.y}px, 0)`, opacity: point.visible ? "1" : "0" };
}

function focusStage(stage: CreativeProgressionStage): void {
  emit("focus", stage.anchorNodeId);
}
</script>

<template>
  <div class="creative-progression-layer" aria-label="创作进阶星链">
    <svg class="creative-progression-links" aria-hidden="true">
      <defs>
        <linearGradient id="creative-progression-flow" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0" stop-color="var(--orrery-canon)" stop-opacity=".28" />
          <stop offset=".52" stop-color="var(--orrery-core)" stop-opacity=".8" />
          <stop offset="1" stop-color="var(--orrery-branch)" stop-opacity=".3" />
        </linearGradient>
      </defs>
      <path
        v-for="link in progression.links"
        :key="`${link.source}:${link.target}`"
        class="creative-progression-link"
        :class="`is-${link.state}`"
        :d="linkPath(link.source, link.target)"
      />
    </svg>
    <button
      v-for="point in stagePoints"
      :key="point.stage.id"
      class="creative-progression-stage"
      :class="`is-${point.stage.state}`"
      :style="styleFor(point)"
      :aria-label="`${point.stage.title}：${point.stage.description}`"
      :disabled="!point.stage.anchorNodeId"
      @click="focusStage(point.stage)"
    >
      <span class="creative-progression-orbit" aria-hidden="true"><i></i><b></b></span>
      <span class="creative-progression-copy">
        <small>{{ point.stage.kicker }}</small>
        <strong>{{ point.stage.title }}</strong>
        <em>{{ point.stage.completion }}%</em>
      </span>
    </button>
  </div>
</template>
