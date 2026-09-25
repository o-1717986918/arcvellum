import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import type { EventStreamConnection } from "@/services/api";
import { friendlyError } from "@/stores/app";
import { applyCreativeEvent } from "../projection";
import { inheritedTextChange } from "../revisionComparison";
import { creativeLiveClient } from "../services/creativeLiveClient";
import type { ArtifactRevision, ArtifactRevisionSummary, CreativeContextSummary, CreativeLiveSnapshot } from "../types";

export const useCreativeLiveStore = defineStore("creative-live", () => {
  const snapshot = shallowRef<CreativeLiveSnapshot | null>(null);
  const projectRoot = ref("");
  const selectedArtifactId = ref("");
  const selectedSessionId = ref("");
  const loading = ref(false);
  const connected = ref(false);
  const error = ref("");
  const revisions = ref<ArtifactRevisionSummary[]>([]);
  const selectedRevision = shallowRef<ArtifactRevision | null>(null);
  const comparisonRevision = shallowRef<ArtifactRevision | null>(null);
  const sessionContexts = ref<Record<string, CreativeContextSummary | null>>({});
  let selectionPinned = false;
  let connection: EventStreamConnection | null = null;
  let connectionGeneration = 0;
  let revisionGeneration = 0;
  let frame = 0;
  let pendingEvents: Parameters<typeof applyCreativeEvent>[1][] = [];

  const activeArtifact = computed(() => (snapshot.value?.artifacts || []).find((item) => item.artifact_id === selectedArtifactId.value) || snapshot.value?.artifacts?.[0] || null);
  const activeSession = computed(() => {
    const base = (snapshot.value?.sessions || []).find((item) => item.session_id === selectedSessionId.value) || snapshot.value?.sessions?.[0] || null;
    return base ? { ...base, context: sessionContexts.value[base.session_id] || base.context } : null;
  });
  const proseIsStreaming = computed(() => activeArtifact.value?.identity === "streaming_preview" && activeArtifact.value?.kind === "prose");

  async function connect(root: string, force = false): Promise<void> {
    if (!root) return;
    if (!force && projectRoot.value === root && connection) return;
    disconnect();
    const generation = connectionGeneration;
    projectRoot.value = root;
    selectionPinned = false;
    sessionContexts.value = {};
    loading.value = true;
    error.value = "";
    try {
      const initial = await creativeLiveClient.snapshot(root);
      if (generation !== connectionGeneration) return;
      applySnapshot(initial);
      connection = creativeLiveClient.observe(root, applySnapshot, (event) => {
        if (projectRoot.value !== root || !snapshot.value) return;
        pendingEvents.push(event);
        scheduleFlush();
        connected.value = true;
      }, (cause) => {
        if (projectRoot.value === root) error.value = friendlyError(cause, "创作现场正在重新连接。");
      });
      connected.value = true;
    } catch (cause) {
      if (generation === connectionGeneration) error.value = friendlyError(cause, "创作现场暂时不可用。");
    } finally {
      if (generation === connectionGeneration) loading.value = false;
    }
  }

  async function reconnect(root = projectRoot.value): Promise<void> {
    await connect(root, true);
  }

  function applySnapshot(value: CreativeLiveSnapshot): void {
    const normalized = {
      ...value,
      artifacts: Array.isArray(value.artifacts) ? value.artifacts : [],
      sessions: Array.isArray(value.sessions) ? value.sessions : [],
      activity: Array.isArray(value.activity) ? value.activity : [],
      reviews: Array.isArray(value.reviews) ? value.reviews : [],
      active_scene_transaction: value.active_scene_transaction || null,
      scene_transactions: Array.isArray(value.scene_transactions) ? value.scene_transactions : [],
      style_provenance: value.style_provenance || null,
      events: Array.isArray(value.events) ? value.events : [],
      usage: value.usage || { total_tokens: 0, cost_usd: 0, updates: 0 },
      cursor: Number(value.cursor || 0),
      live_cursor: Number(value.live_cursor || 0),
    };
    snapshot.value = normalized;
    connected.value = true;
    if (!selectionPinned || !normalized.artifacts.some((item) => item.artifact_id === selectedArtifactId.value)) {
      selectedArtifactId.value = normalized.artifacts[0]?.artifact_id || "";
    }
    if (!normalized.sessions.some((item) => item.session_id === selectedSessionId.value)) {
      selectedSessionId.value = normalized.sessions[0]?.session_id || "";
    }
  }

  function selectArtifact(artifactId: string): void {
    revisionGeneration += 1;
    selectionPinned = true;
    selectedArtifactId.value = artifactId;
    revisions.value = [];
    selectedRevision.value = null;
    comparisonRevision.value = null;
  }

  async function selectSession(sessionId: string): Promise<void> {
    selectedSessionId.value = sessionId;
    if (!projectRoot.value || sessionContexts.value[sessionId] !== undefined) return;
    try {
      const response = await creativeLiveClient.session(projectRoot.value, sessionId);
      sessionContexts.value = { ...sessionContexts.value, [sessionId]: response.session.context || null };
    } catch (cause) {
      error.value = friendlyError(cause, "会话资料摘要暂时无法读取。");
    }
  }

  async function loadRevisions(): Promise<void> {
    const artifact = activeArtifact.value;
    if (!artifact || !projectRoot.value) return;
    const response = await creativeLiveClient.revisions(projectRoot.value, artifact.artifact_id);
    revisions.value = response.revisions || [];
  }

  async function loadRevision(revisionId: string): Promise<void> {
    const artifact = activeArtifact.value;
    if (!artifact || !projectRoot.value) return;
    const generation = ++revisionGeneration;
    const root = projectRoot.value;
    comparisonRevision.value = null;
    const response = await creativeLiveClient.revision(root, artifact.artifact_id, revisionId);
    if (generation !== revisionGeneration) return;
    selectedRevision.value = response.revision;
    const inherited = inheritedTextChange(revisions.value, response.revision);
    if (!inherited) return;
    try {
      const prior = await creativeLiveClient.revision(root, artifact.artifact_id, inherited.revision_id);
      if (generation === revisionGeneration && prior.revision.diff.trim()) comparisonRevision.value = prior.revision;
    } catch (cause) {
      if (generation === revisionGeneration) error.value = friendlyError(cause, "修订对照暂时无法读取。正文版本仍可阅读。");
    }
  }

  function disconnect(): void {
    connectionGeneration += 1;
    revisionGeneration += 1;
    connection?.close();
    connection = null;
    if (frame) window.cancelAnimationFrame(frame);
    frame = 0;
    pendingEvents = [];
    connected.value = false;
  }

  function scheduleFlush(): void {
    if (frame) return;
    frame = window.requestAnimationFrame(() => {
      frame = 0;
      if (!snapshot.value || !pendingEvents.length) return;
      const events = pendingEvents;
      pendingEvents = [];
      snapshot.value = events.reduce(applyCreativeEvent, snapshot.value);
      if (!selectionPinned) {
        const latestArtifact = [...events].reverse().find((event) => event.artifact)?.artifact;
        if (latestArtifact) selectedArtifactId.value = latestArtifact.artifact_id;
      }
    });
  }

  function reset(): void {
    disconnect();
    snapshot.value = null;
    projectRoot.value = "";
    selectedArtifactId.value = "";
    selectedSessionId.value = "";
    revisions.value = [];
    selectedRevision.value = null;
    comparisonRevision.value = null;
    sessionContexts.value = {};
    selectionPinned = false;
    error.value = "";
  }

  return {
    snapshot, projectRoot, selectedArtifactId, selectedSessionId, loading, connected, error,
    revisions, selectedRevision, comparisonRevision, activeArtifact, activeSession, proseIsStreaming,
    connect, reconnect, selectArtifact, selectSession, loadRevisions, loadRevision, disconnect, reset,
  };
});
