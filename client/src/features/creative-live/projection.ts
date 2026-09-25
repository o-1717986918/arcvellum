import type {
  CreativeActivity,
  CreativeArtifact,
  CreativeLiveEvent,
  CreativeLiveSnapshot,
  CreativeSession,
  SceneTransactionSummary,
} from "./types";

const MAX_ARTIFACT_CHARS = 2_000_000;
const MAX_TRANSCRIPT_CHARS = 120_000;

export function applyCreativeEvent(snapshot: CreativeLiveSnapshot, event: CreativeLiveEvent): CreativeLiveSnapshot {
  if (event.sequence && event.sequence <= Number(snapshot.live_cursor || 0)) return snapshot;
  if (snapshot.events.some((item) => item.event_id === event.event_id)) return snapshot;
  const artifacts = reduceArtifact(snapshot.artifacts, event);
  const sessions = reduceSession(snapshot.sessions, event);
  const activity = event.channel === "activity" || event.channel === "control" || event.channel === "artifact" || event.channel === "review"
    ? [...snapshot.activity, activityFrom(event)].slice(-120)
    : snapshot.activity;
  const reviews = event.channel === "review"
    ? [...snapshot.reviews, reviewFrom(event)].slice(-120)
    : snapshot.reviews;
  const usage = event.channel === "usage" ? reduceUsage(snapshot.usage, event) : snapshot.usage;
  const transaction = transactionFrom(event, snapshot.active_scene_transaction);
  const sceneTransactions = transaction
    ? reduceSceneTransactions(snapshot.scene_transactions || [], transaction)
    : snapshot.scene_transactions || [];
  return {
    ...snapshot,
    status: event.event === "task.started" ? "active" : snapshot.status,
    artifacts,
    sessions,
    activity,
    reviews,
    usage,
    active_scene_transaction: transaction || snapshot.active_scene_transaction || null,
    scene_transactions: sceneTransactions,
    events: [...snapshot.events, event].slice(-240),
    cursor: Math.max(snapshot.cursor, Number(event.sequence || 0)),
    live_cursor: Math.max(Number(snapshot.live_cursor || 0), Number(event.sequence || 0)),
  };
}

function transactionFrom(
  event: CreativeLiveEvent,
  previous: SceneTransactionSummary | null,
): SceneTransactionSummary | null {
  const transactionId = String(event.data.scene_transaction_id || event.data.transaction_id || "");
  if (!transactionId) return null;
  const same = previous?.transaction_id === transactionId ? previous : null;
  return {
    transaction_id: transactionId,
    scene_id: String(event.data.scene_id || same?.scene_id || ""),
    status: String(event.data.status || same?.status || "prepared"),
    mode: String(event.data.mode || same?.mode || "standard"),
    risk: riskValue(event.data.risk || same?.risk),
    objective: String(event.data.objective || same?.objective || ""),
    scene_function: String(event.data.scene_function || same?.scene_function || ""),
    body_hanzi: nonNegative(event.data.body_hanzi ?? same?.body_hanzi),
    warning_count: nonNegative(event.data.warning_count ?? same?.warning_count),
    hard_issue_count: nonNegative(event.data.hard_issue_count ?? same?.hard_issue_count),
    review_decision: String(event.data.review_decision || same?.review_decision || ""),
    review_summary: String(event.data.review_summary || same?.review_summary || ""),
    revision_attempts: nonNegative(event.data.revision_attempts ?? same?.revision_attempts),
    requires_input: Boolean(event.data.requires_input ?? same?.requires_input),
    message: String(event.data.message || same?.message || ""),
    version: nonNegative(event.data.version ?? same?.version),
  };
}

function reduceSceneTransactions(
  items: SceneTransactionSummary[],
  transaction: SceneTransactionSummary,
): SceneTransactionSummary[] {
  return [
    transaction,
    ...items.filter((item) => item.transaction_id !== transaction.transaction_id),
  ].slice(0, 80);
}

function riskValue(value: unknown): SceneTransactionSummary["risk"] {
  return value === "low" || value === "high" ? value : "standard";
}

function nonNegative(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
}

function reduceArtifact(items: CreativeArtifact[], event: CreativeLiveEvent): CreativeArtifact[] {
  if (!event.artifact) return items;
  const index = items.findIndex((item) => item.artifact_id === event.artifact?.artifact_id);
  const previous = index >= 0 ? items[index] : null;
  const content = typeof event.data.content === "string"
    ? event.data.content.slice(0, MAX_ARTIFACT_CHARS)
    : `${previous?.content || ""}${typeof event.data.delta === "string" ? event.data.delta : ""}`.slice(-MAX_ARTIFACT_CHARS);
  const next: CreativeArtifact = {
    ...(previous || { content: "", updated_at: "", source_event: "" }),
    ...event.artifact,
    content,
    updated_at: event.at,
    source_event: event.event,
    truncated: content.length >= MAX_ARTIFACT_CHARS,
  };
  const result = index >= 0 ? items.map((item, itemIndex) => itemIndex === index ? next : item) : [next, ...items];
  return result.sort((left, right) => String(right.updated_at).localeCompare(String(left.updated_at)));
}

function reduceSession(items: CreativeSession[], event: CreativeLiveEvent): CreativeSession[] {
  const sessionId = event.session_id || event.run_id;
  if (!sessionId) return items;
  const index = items.findIndex((item) => item.session_id === sessionId);
  const previous: CreativeSession = index >= 0 ? items[index] : {
    session_id: sessionId,
    role: "worker",
    runtime: "",
    status: "running",
    route: event.route,
    task_id: event.task_id,
    transcript: "",
    tools: [],
  };
  const transcript = event.event === "agent.message.delta"
    ? `${previous.transcript || ""}${String(event.data.text || "")}`.slice(-MAX_TRANSCRIPT_CHARS)
    : previous.transcript || "";
  const tools = event.event.startsWith("tool.")
    ? [...(previous.tools || []), { event: event.event, tool: String(event.data.tool || ""), status: String(event.data.status || ""), at: event.at }].slice(-40)
    : previous.tools || [];
  const next: CreativeSession = {
    ...previous,
    route: event.route || previous.route,
    task_id: event.task_id || previous.task_id,
    runtime: String(event.data.runtime || previous.runtime || ""),
    status: event.event === "runner.session.finished" ? String(event.data.status || "complete") : previous.status,
    transcript,
    tools,
    updated_at: event.at,
    last_event: event.event,
  };
  const result = index >= 0 ? items.map((item, itemIndex) => itemIndex === index ? next : item) : [next, ...items];
  return result.sort((left, right) => String(right.updated_at || "").localeCompare(String(left.updated_at || "")));
}

function activityFrom(event: CreativeLiveEvent): CreativeActivity {
  return {
    event_id: event.event_id,
    event: event.event,
    channel: event.channel,
    at: event.at,
    task_id: event.task_id,
    route: event.route,
    title: String(event.data.title || "创作现场更新"),
    message: String(event.data.message || "项目状态已有新变化。"),
  };
}

function reviewFrom(event: CreativeLiveEvent) {
  return {
    ...activityFrom(event),
    status: String(event.data.status || ""),
    findings: Array.isArray(event.data.findings) ? event.data.findings : [],
    artifact_id: event.artifact?.artifact_id || "",
  };
}

function reduceUsage(current: CreativeLiveSnapshot["usage"], event: CreativeLiveEvent): CreativeLiveSnapshot["usage"] {
  const usage = typeof event.data.usage === "object" && event.data.usage ? event.data.usage as Record<string, unknown> : {};
  return {
    total_tokens: current.total_tokens + Number(usage.total_tokens || 0),
    cost_usd: current.cost_usd + Number(event.data.cost_usd || 0),
    updates: current.updates + 1,
  };
}
