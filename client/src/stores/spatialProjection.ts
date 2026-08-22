import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { orreryClient } from "@/features/orrery/services/orreryClient";
import type { NarrativeFocusLevel } from "@/features/orrery/model/focusScope";
import type { SpatialGrammar, SpatialNarrativeProjection, SpatialNarrativeProjectionPatch } from "@/types/spatial";
import { defaultObservation } from "@/features/orrery/layout/observationWindow";
import { applySpatialProjectionPatch } from "@/features/orrery/model/projectionPatch";

// Open with the full celestial shell. The chapter rail preserves exact order,
// while the first frame gains the spatial depth expected from the observatory.
const DEFAULT_GRAMMAR: SpatialGrammar = "constellation";
type NarrativeViewTarget = { level: NarrativeFocusLevel; focus: string };

export const useSpatialProjectionStore = defineStore("spatialProjection", () => {
  const projection = shallowRef<SpatialNarrativeProjection | null>(null);
  const loading = ref(false);
  const error = ref("");
  const level = ref<NarrativeFocusLevel>("book");
  const focus = ref("");
  const focusHistory = ref<NarrativeViewTarget[]>([]);
  const canGoBack = computed(() => focusHistory.value.length > 0);
  const grammar = ref<SpatialGrammar>(DEFAULT_GRAMMAR);
  const projectRoot = ref("");
  const timeCursor = ref(0);
  const timeWindow = ref(3);
  const cameraPreset = ref<"recommended" | "front" | "current-chapter" | "custom">("recommended");
  let observationProject = "";
  let stream: { close(): void } | null = null;
  let requestSequence = 0;

  async function open(root: string, next: Partial<{ level: NarrativeFocusLevel; focus: string; grammar: SpatialGrammar }> = {}): Promise<void> {
    if (projectRoot.value !== root) focusHistory.value = [];
    projectRoot.value = root;
    level.value = next.level || level.value;
    focus.value = next.focus ?? focus.value;
    grammar.value = next.grammar || grammar.value;
    await refresh();
    startStream();
  }

  async function refresh(): Promise<void> {
    if (!projectRoot.value) return;
    const sequence = ++requestSequence;
    loading.value = true;
    error.value = "";
    try {
      const payload = await orreryClient.spatialProjection(viewQuery());
      if (sequence === requestSequence) {
        applyProjection(payload);
      }
    } catch (cause) {
      if (sequence === requestSequence) error.value = cause instanceof Error ? cause.message : "无法读取叙事场域。";
    } finally {
      if (sequence === requestSequence) loading.value = false;
    }
  }

  async function setView(next: { level?: NarrativeFocusLevel; focus?: string; grammar?: SpatialGrammar }): Promise<void> {
    const previous = { level: level.value, focus: focus.value };
    const nextLevel = next.level || level.value;
    const nextFocus = next.focus !== undefined ? next.focus : focus.value;
    if (previous.level !== nextLevel || previous.focus !== nextFocus) {
      focusHistory.value = [...focusHistory.value.slice(-31), previous];
    }
    if (next.level) level.value = next.level;
    if (next.focus !== undefined) focus.value = next.focus;
    if (next.grammar) grammar.value = next.grammar;
    await refresh();
    startStream();
  }

  async function goBack(): Promise<void> {
    const previous = focusHistory.value.at(-1);
    if (!previous) return;
    focusHistory.value = focusHistory.value.slice(0, -1);
    level.value = previous.level;
    focus.value = previous.focus;
    await refresh();
    startStream();
  }

  function startStream(): void {
    stream?.close();
    if (!projectRoot.value) return;
    const expectedRoot = projectRoot.value;
    const expectedKey = viewKey();
    stream = orreryClient.observeSpatialProjection(viewQuery(), (payload) => {
      if (projectRoot.value !== expectedRoot || viewKey() !== expectedKey) return;
      const current = projection.value;
      if (current && payload.sequence < current.sequence) return;
      applyProjection(payload);
    }, (patch) => {
      if (projectRoot.value !== expectedRoot || viewKey() !== expectedKey) return;
      applyPatch(patch);
    }, (cause) => {
      if (projectRoot.value === expectedRoot) error.value = cause instanceof Error ? cause.message : "叙事场域连接暂时中断。";
    });
  }

  function close(): void {
    stream?.close();
    stream = null;
    projection.value = null;
    error.value = "";
    observationProject = "";
    focusHistory.value = [];
  }

  function viewQuery() {
    return { projectRoot: projectRoot.value, level: level.value, focus: focus.value, grammar: grammar.value };
  }

  function viewKey(): string {
    return JSON.stringify(viewQuery());
  }

  function initializeObservation(payload: SpatialNarrativeProjection): void {
    if (observationProject === projectRoot.value) return;
    const observation = defaultObservation(payload.nodes);
    timeCursor.value = observation.cursor;
    timeWindow.value = observation.window;
    cameraPreset.value = "recommended";
    observationProject = projectRoot.value;
  }

  function applyProjection(payload: SpatialNarrativeProjection): void {
    const current = projection.value;
    const currentRevision = current?.projection_revision || current?.revision || "";
    const nextRevision = payload.projection_revision || payload.revision || "";
    const sameView = current
      && current.level === payload.level
      && current.focus === payload.focus
      && current.spatial_grammar === payload.spatial_grammar;
    if (current && sameView && currentRevision && currentRevision === nextRevision) return;
    projection.value = payload;
    initializeObservation(payload);
  }

  function applyPatch(patch: SpatialNarrativeProjectionPatch): void {
    const current = projection.value;
    if (!current) {
      void refresh();
      return;
    }
    if (patch.sequence < current.sequence) return;
    const currentRevision = current.projection_revision || current.revision;
    if (patch.target_revision === currentRevision) return;
    try {
      applyProjection(applySpatialProjectionPatch(current, patch));
    } catch {
      void refresh();
    }
  }

  function setObservation(next: { cursor?: number; window?: number }): void {
    if (next.cursor !== undefined && Number.isFinite(next.cursor)) timeCursor.value = next.cursor;
    if (next.window !== undefined && Number.isFinite(next.window)) timeWindow.value = Math.max(0.5, next.window);
  }

  function setCameraPreset(value: "recommended" | "front" | "current-chapter" | "custom"): void {
    cameraPreset.value = value;
  }

  return {
    projection, loading, error, level, focus, grammar, projectRoot,
    focusHistory, canGoBack, timeCursor, timeWindow, cameraPreset,
    open, refresh, setView, goBack, setObservation, setCameraPreset, close,
  };
});
