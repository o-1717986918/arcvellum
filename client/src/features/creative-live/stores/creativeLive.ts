import { computed, ref, shallowRef } from "vue";
import { defineStore } from "pinia";
import type { EventStreamConnection } from "@/services/api";
import { friendlyError } from "@/stores/app";
import { applyCreativeEvent } from "../projection";
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
  const sessionContexts = ref<Record<string, CreativeContextSummary | null>>({});
  let selectionPinned = false;
  let connection: EventStreamConnection | null = null;
  let frame = 0;
  let pendingEvents: Parameters<typeof applyCreativeEvent>[1][] = [];

  const activeArtifact = computed(() => (snapshot.value?.artifacts || []).find((item) => item.artifact_id === selectedArtifactId.value) || snapshot.value?.artifacts?.[0] || null);
  const activeSession = computed(() => {
    const base = (snapshot.value?.sessions || []).find((item) => item.session_id === selectedSessionId.value) || snapshot.value?.sessions?.[0] || null;
    return base ? { ...base, context: sessionContexts.value[base.session_id] || base.context } : null;
  });
  const proseIsStreaming = computed(() => activeArtifact.value?.identity === "streaming_preview" && activeArtifact.value?.kind === "prose");

  async function connect(root: string): Promise<void> {
    if (!root) return;
    if (projectRoot.value === root && connection) return;
    disconnect();
    projectRoot.value = root;
    selectionPinned = false;
    sessionContexts.value = {};
    loading.value = true;
    error.value = "";
    try {
      applySnapshot(await creativeLiveClient.snapshot(root));
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
      error.value = friendlyError(cause, "创作现场暂时不可用。");
    } finally {
      loading.value = false;
    }
  }

  function applySnapshot(value: CreativeLiveSnapshot): void {
    const normalized = {
      ...value,
      artifacts: Array.isArray(value.artifacts) ? value.artifacts : [],
      sessions: Array.isArray(value.sessions) ? value.sessions : [],
      activity: Array.isArray(value.activity) ? value.activity : [],
      reviews: Array.isArray(value.reviews) ? value.reviews : [],
      events: Array.isArray(value.events) ? value.events : [],
      usage: value.usage || { total_tokens: 0, cost_usd: 0, updates: 0 },
      cursor: Number(value.cursor || 0),
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
    selectionPinned = true;
    selectedArtifactId.value = artifactId;
    revisions.value = [];
    selectedRevision.value = null;
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
    const response = await creativeLiveClient.revision(projectRoot.value, artifact.artifact_id, revisionId);
    selectedRevision.value = response.revision;
  }

  function disconnect(): void {
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
    sessionContexts.value = {};
    selectionPinned = false;
    error.value = "";
  }

  return {
    snapshot, projectRoot, selectedArtifactId, selectedSessionId, loading, connected, error,
    revisions, selectedRevision, activeArtifact, activeSession, proseIsStreaming,
    connect, selectArtifact, selectSession, loadRevisions, loadRevision, disconnect, reset,
  };
});
