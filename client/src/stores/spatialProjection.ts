import { ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import { api, connectEventStream, query, type EventStreamConnection } from "@/services/api";
import type { SpatialGrammar, SpatialNarrativeProjection } from "@/types/spatial";
import { defaultObservation } from "@/features/orrery/layout/observationWindow";

const DEFAULT_GRAMMAR: SpatialGrammar = "spine";

export const useSpatialProjectionStore = defineStore("spatialProjection", () => {
  const projection = shallowRef<SpatialNarrativeProjection | null>(null);
  const loading = ref(false);
  const error = ref("");
  const level = ref<"book" | "chapter" | "scene">("book");
  const focus = ref("");
  const grammar = ref<SpatialGrammar>(DEFAULT_GRAMMAR);
  const projectRoot = ref("");
  const timeCursor = ref(0);
  const timeWindow = ref(3);
  const cameraPreset = ref<"recommended" | "front" | "current-chapter" | "custom">("recommended");
  let observationProject = "";
  let stream: EventStreamConnection | null = null;
  let requestSequence = 0;

  async function open(root: string, next: Partial<{ level: "book" | "chapter" | "scene"; focus: string; grammar: SpatialGrammar }> = {}): Promise<void> {
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
      const payload = await api<SpatialNarrativeProjection>(`/narrative/projection/v3?${params()}`);
      if (sequence === requestSequence) {
        projection.value = payload;
        initializeObservation(payload);
      }
    } catch (cause) {
      if (sequence === requestSequence) error.value = cause instanceof Error ? cause.message : "无法读取叙事场域。";
    } finally {
      if (sequence === requestSequence) loading.value = false;
    }
  }

  async function setView(next: { level?: "book" | "chapter" | "scene"; focus?: string; grammar?: SpatialGrammar }): Promise<void> {
    if (next.level) level.value = next.level;
    if (next.focus !== undefined) focus.value = next.focus;
    if (next.grammar) grammar.value = next.grammar;
    await refresh();
    startStream();
  }

  function startStream(): void {
    stream?.close();
    if (!projectRoot.value) return;
    const expectedRoot = projectRoot.value;
    const expectedKey = params();
    stream = connectEventStream(`/narrative/stream/v3?${expectedKey}&interval_seconds=2`, (event, data) => {
      if (event !== "narrative.v3.projection" || projectRoot.value !== expectedRoot || params() !== expectedKey) return;
      const payload = data as unknown as SpatialNarrativeProjection;
      const current = projection.value;
      if (current && payload.sequence < current.sequence) return;
      projection.value = payload;
      initializeObservation(payload);
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
  }

  function params(): string {
    return query({ project_root: projectRoot.value, level: level.value, focus: focus.value, grammar: grammar.value });
  }

  function initializeObservation(payload: SpatialNarrativeProjection): void {
    if (observationProject === projectRoot.value) return;
    const observation = defaultObservation(payload.nodes);
    timeCursor.value = observation.cursor;
    timeWindow.value = observation.window;
    cameraPreset.value = "recommended";
    observationProject = projectRoot.value;
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
    timeCursor, timeWindow, cameraPreset,
    open, refresh, setView, setObservation, setCameraPreset, close,
  };
});
