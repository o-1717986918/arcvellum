import type { AgentEvent } from "@earendil-works/pi-agent-core";
import type { RuntimeEventSink, WorkerState } from "./contracts.ts";
import type { ArtifactPreviewExtractor } from "./artifact-preview.ts";

export class WorkerEventAdapter {
	private pendingReasoningEvents = 0;
	private pendingReasoningCharacters = 0;
	private lastReasoningEmit = 0;
	private reasoningActive = false;
	private pendingText = "";
	private pendingTextEvents = 0;
	private lastTextEmit = 0;
	private messageIndex = 0;
	private readonly sessionId: string;
	private readonly state: WorkerState;
	private readonly emit: RuntimeEventSink;
	private readonly artifactPreview?: ArtifactPreviewExtractor;

	constructor(
		sessionId: string,
		state: WorkerState,
		emit: RuntimeEventSink,
		artifactPreview?: ArtifactPreviewExtractor,
	) {
		this.sessionId = sessionId;
		this.state = state;
		this.emit = emit;
		this.artifactPreview = artifactPreview;
	}

	handle(event: AgentEvent): void {
		if (event.type === "agent_start") {
			this.emit("runner.session.created", { session_id: this.sessionId, ephemeral: true });
			return;
		}
		if (event.type === "agent_end") {
			this.flushReasoning(true);
			this.flushText(true);
			this.emit("runner.session.finished", { session_id: this.sessionId });
			return;
		}
		if (event.type === "turn_start") {
			this.emit("runner.session.status", { session_id: this.sessionId, status: "running" });
			return;
		}
		if (event.type === "turn_end") {
			this.flushReasoning(true);
			this.flushText(true);
			this.state.turns += 1;
			return;
		}
		if (event.type === "tool_execution_start") {
			this.flushReasoning(true);
			this.flushText(true);
			this.state.toolCalls += 1;
			this.emit("tool.started", { tool: event.toolName, tool_use_id: event.toolCallId });
			return;
		}
		if (event.type === "tool_execution_end") {
			const reason = event.isError ? toolErrorReason(event.result) : "";
			this.state.lastToolError = event.isError
				? { tool: event.toolName, reason }
				: null;
			this.emit(event.isError ? "tool.denied" : "tool.completed", {
				tool: event.toolName,
				tool_use_id: event.toolCallId,
				status: event.isError ? "error" : "completed",
				...(event.isError ? { reason } : {}),
			});
			return;
		}
		if (event.type === "message_update") {
			this.handleMessageUpdate(event.assistantMessageEvent as unknown);
			return;
		}
		if (event.type === "message_end" && isRecord(event.message) && event.message.role === "assistant") {
			this.flushReasoning(true);
			this.flushText(true);
			this.messageIndex += 1;
			this.emitUsage(event.message, this.messageIndex);
			this.emit("agent.message.completed", { session_id: this.sessionId });
		}
	}

	providerRequest(provider: string, model: string): void {
		this.state.providerRequests += 1;
		this.emit("runner.provider.request.started", { session_id: this.sessionId, provider, model });
	}

	private handleMessageUpdate(value: unknown): void {
		if (!isRecord(value)) return;
		this.artifactPreview?.handle(value);
		const type = String(value.type ?? "");
		const delta = typeof value.delta === "string" ? value.delta : "";
		if (type === "thinking_delta") {
			this.flushText(true);
			if (!this.reasoningActive) {
				this.reasoningActive = true;
				this.lastReasoningEmit = Date.now();
				this.emit("runner.reasoning.started", { session_id: this.sessionId });
			}
			this.pendingReasoningEvents += 1;
			this.pendingReasoningCharacters += delta.length;
			this.state.reasoningCharacters += delta.length;
			this.flushReasoning(false);
			return;
		}
		if (type === "text_delta" && delta) {
			this.flushReasoning(true);
			this.state.textCharacters += delta.length;
			if (!this.pendingText) this.lastTextEmit = Date.now();
			this.pendingText += delta;
			this.pendingTextEvents += 1;
			this.flushText(false);
		}
	}

	private flushReasoning(force: boolean): void {
		const now = Date.now();
		if (
			this.pendingReasoningEvents > 0
			&& (force || this.pendingReasoningCharacters >= 512 || now - this.lastReasoningEmit >= 750)
		) {
			this.emit("runner.reasoning.activity", {
				session_id: this.sessionId,
				delta_events: this.pendingReasoningEvents,
				delta_characters: this.pendingReasoningCharacters,
			});
			this.pendingReasoningEvents = 0;
			this.pendingReasoningCharacters = 0;
			this.lastReasoningEmit = now;
		}
		if (force && this.reasoningActive) {
			this.emit("runner.reasoning.completed", { session_id: this.sessionId });
			this.reasoningActive = false;
		}
	}

	private flushText(force: boolean): void {
		if (!this.pendingText) return;
		const now = Date.now();
		if (!force && this.pendingText.length < 256 && now - this.lastTextEmit < 250) return;
		this.emit("agent.message.delta", {
			session_id: this.sessionId,
			text: this.pendingText,
			delta_events: this.pendingTextEvents,
		});
		this.pendingText = "";
		this.pendingTextEvents = 0;
		this.lastTextEmit = now;
	}

	private emitUsage(message: Record<string, unknown>, index: number): void {
		const usage = isRecord(message.usage) ? message.usage : {};
		const cost = isRecord(usage.cost) ? usage.cost : {};
		if (typeof usage.reasoning === "number" && Number.isFinite(usage.reasoning)) {
			this.state.reasoningTokens += usage.reasoning;
			this.state.reasoningTokensReported = true;
		}
		this.emit("usage.updated", {
			session_id: this.sessionId,
			usage_id: `${this.sessionId}-${index}`,
			provider: String(message.provider ?? ""),
			model: String(message.model ?? ""),
			usage: {
				input: numberValue(usage.input),
				output: numberValue(usage.output),
				reasoning: typeof usage.reasoning === "number" ? usage.reasoning : undefined,
				cache_read: numberValue(usage.cacheRead),
				cache_write: numberValue(usage.cacheWrite),
				total_tokens: numberValue(usage.totalTokens),
			},
			cost_usd: numberValue(cost.total),
		});
	}
}

function toolErrorReason(value: unknown): string {
	let reason = "tool execution failed";
	if (isRecord(value)) {
		if (typeof value.error === "string") reason = value.error;
		else if (typeof value.message === "string") reason = value.message;
		else if (Array.isArray(value.content)) {
			const text = value.content
				.filter(isRecord)
				.map((item) => typeof item.text === "string" ? item.text : "")
				.find(Boolean);
			if (text) reason = text;
		}
	}
	return reason
		.replace(/[A-Za-z]:[\\/][^\s'"`]+/g, "<redacted-path>")
		.replace(/sk-[A-Za-z0-9_-]{20,}/g, "<redacted-secret>")
		.replace(/[\r\n\t]+/g, " ")
		.replace(/\s+/g, " ")
		.trim()
		.slice(0, 500) || "tool execution failed";
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}

function numberValue(value: unknown): number {
	return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
