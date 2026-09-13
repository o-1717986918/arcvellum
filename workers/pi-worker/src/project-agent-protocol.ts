import { randomUUID } from "node:crypto";

export const PROJECT_AGENT_BRIDGE_SCHEMA = "arcvellum/project-agent-bridge/v1";
export const MAX_BRIDGE_FRAME_BYTES = 256 * 1024;
export const MAX_TOOL_RESULT_BYTES = 64 * 1024;

export type BridgeMessageType =
	| "turn.start"
	| "turn.cancel"
	| "bridge.ready"
	| "agent.event"
	| "tool.call"
	| "tool.result"
	| "turn.complete"
	| "bridge.error";

const MESSAGE_TYPES = new Set<BridgeMessageType>([
	"turn.start",
	"turn.cancel",
	"bridge.ready",
	"agent.event",
	"tool.call",
	"tool.result",
	"turn.complete",
	"bridge.error",
]);

export interface BridgeEnvelope<T extends Record<string, unknown> = Record<string, unknown>> {
	schema: typeof PROJECT_AGENT_BRIDGE_SCHEMA;
	type: BridgeMessageType;
	message_id: string;
	turn_id: string;
	payload: T;
}

export type BridgeWriter = (envelope: BridgeEnvelope) => void;

export function envelope(
	type: BridgeMessageType,
	turnId: string,
	payload: Record<string, unknown> = {},
	messageId = `message-${randomUUID()}`,
): BridgeEnvelope {
	if (!turnId.trim()) throw new Error("bridge turn_id is required");
	return {
		schema: PROJECT_AGENT_BRIDGE_SCHEMA,
		type,
		message_id: messageId,
		turn_id: turnId,
		payload,
	};
}

export function encodeEnvelope(value: BridgeEnvelope): string {
	return `${JSON.stringify(value)}\n`;
}

export function parseEnvelopeLine(line: string): BridgeEnvelope {
	if (Buffer.byteLength(line, "utf8") > MAX_BRIDGE_FRAME_BYTES) {
		throw new Error(`bridge frame exceeds ${MAX_BRIDGE_FRAME_BYTES} bytes`);
	}
	let decoded: unknown;
	try {
		decoded = JSON.parse(line);
	} catch {
		throw new Error("bridge frame must be valid JSON");
	}
	if (!isRecord(decoded)) throw new Error("bridge frame must be an object");
	if (decoded.schema !== PROJECT_AGENT_BRIDGE_SCHEMA) {
		throw new Error(`unsupported Project Agent bridge schema: ${String(decoded.schema || "")}`);
	}
	if (typeof decoded.type !== "string" || !MESSAGE_TYPES.has(decoded.type as BridgeMessageType)) {
		throw new Error(`unsupported bridge message type: ${String(decoded.type || "")}`);
	}
	if (!nonEmptyString(decoded.message_id) || !nonEmptyString(decoded.turn_id)) {
		throw new Error("bridge message_id and turn_id are required");
	}
	if (!isRecord(decoded.payload)) throw new Error("bridge payload must be an object");
	return decoded as unknown as BridgeEnvelope;
}

interface PendingToolCall {
	name: string;
	resolve: (value: unknown) => void;
	reject: (error: Error) => void;
	timer: ReturnType<typeof setTimeout>;
	signal?: AbortSignal;
	onAbort?: () => void;
}

/** One-turn request broker between Pi Agent tools and the Studio host. */
export class ProjectToolBridge {
	private readonly pending = new Map<string, PendingToolCall>();
	private readonly turnId: string;
	private readonly write: BridgeWriter;
	private readonly timeoutMs: number;

	constructor(
		turnId: string,
		write: BridgeWriter,
		timeoutMs = 30_000,
	) {
		if (!turnId.trim()) throw new Error("Project Tool Bridge requires a turn id");
		if (timeoutMs < 1) throw new Error("Project Tool Bridge timeout must be positive");
		this.turnId = turnId;
		this.write = write;
		this.timeoutMs = timeoutMs;
	}

	get pendingCount(): number {
		return this.pending.size;
	}

	request(name: string, args: Record<string, unknown>, signal?: AbortSignal): Promise<unknown> {
		if (!name.trim()) return Promise.reject(new Error("Project Agent tool name is required"));
		if (signal?.aborted) return Promise.reject(abortError("Project Agent tool call cancelled"));
		const requestId = `tool-${randomUUID()}`;
		return new Promise((resolve, reject) => {
			const timer = setTimeout(() => {
				this.rejectPending(requestId, new Error(`Project Agent tool timed out: ${name}`));
			}, this.timeoutMs);
			const pending: PendingToolCall = { name, resolve, reject, timer, signal };
			if (signal) {
				pending.onAbort = () => this.rejectPending(
					requestId,
					abortError(`Project Agent tool cancelled: ${name}`),
				);
				signal.addEventListener("abort", pending.onAbort, { once: true });
			}
			this.pending.set(requestId, pending);
			this.write(envelope("tool.call", this.turnId, {
				request_id: requestId,
				name,
				arguments: args,
			}));
		});
	}

	receive(value: BridgeEnvelope): void {
		if (value.type !== "tool.result") throw new Error("Project Tool Bridge expected tool.result");
		if (value.turn_id !== this.turnId) throw new Error("Project Agent tool result belongs to another turn");
		const requestId = stringField(value.payload, "request_id");
		const name = stringField(value.payload, "name");
		const pending = this.pending.get(requestId);
		if (!pending) throw new Error(`Project Agent tool result has no pending call: ${requestId}`);
		if (pending.name !== name) {
			this.rejectPending(requestId, new Error(`Project Agent tool result name mismatch: ${name}`));
			return;
		}
		const serialized = JSON.stringify(value.payload.result ?? null);
		if (Buffer.byteLength(serialized, "utf8") > MAX_TOOL_RESULT_BYTES) {
			this.rejectPending(requestId, new Error(`Project Agent tool result exceeds ${MAX_TOOL_RESULT_BYTES} bytes`));
			return;
		}
		this.pending.delete(requestId);
		this.cleanup(pending);
		if (value.payload.ok === true) {
			pending.resolve(value.payload.result);
			return;
		}
		pending.reject(new Error(String(value.payload.error || `Project Agent tool failed: ${name}`)));
	}

	cancel(reason = "Project Agent bridge closed"): void {
		for (const requestId of [...this.pending.keys()]) {
			this.rejectPending(requestId, abortError(reason));
		}
	}

	private rejectPending(requestId: string, error: Error): void {
		const pending = this.pending.get(requestId);
		if (!pending) return;
		this.pending.delete(requestId);
		this.cleanup(pending);
		pending.reject(error);
	}

	private cleanup(pending: PendingToolCall): void {
		clearTimeout(pending.timer);
		if (pending.signal && pending.onAbort) {
			pending.signal.removeEventListener("abort", pending.onAbort);
		}
	}
}

function stringField(value: Record<string, unknown>, field: string): string {
	const item = value[field];
	if (!nonEmptyString(item)) throw new Error(`Project Agent bridge field is required: ${field}`);
	return item;
}

function abortError(message: string): Error {
	const error = new Error(message);
	error.name = "AbortError";
	return error;
}

function nonEmptyString(value: unknown): value is string {
	return typeof value === "string" && Boolean(value.trim());
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
