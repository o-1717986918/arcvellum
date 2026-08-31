import type { OutputContract, RuntimeEventSink, TaskContext } from "./contracts.ts";

export type OutputPreviewMode =
	| "prose_stream"
	| "markdown_stream"
	| "semantic_on_commit"
	| "metadata_only"
	| "hidden";

export interface PreviewOutputContract extends OutputContract {
	previewMode: OutputPreviewMode;
}

interface PreviewState {
	content: string;
	revision: number;
}

export class ArtifactPreviewExtractor {
	private readonly outputs: Map<string, PreviewOutputContract>;
	private readonly states = new Map<string, PreviewState>();
	private readonly emit: RuntimeEventSink;

	constructor(context: TaskContext, emit: RuntimeEventSink) {
		this.outputs = new Map(previewOutputContracts(context).map((item) => [item.path, item]));
		this.emit = emit;
	}

	handle(messageEvent: unknown): void {
		if (!isRecord(messageEvent)) return;
		const type = String(messageEvent.type ?? "");
		if (type !== "toolcall_delta" && type !== "toolcall_end") return;
		const index = integerValue(messageEvent.contentIndex);
		const partial = isRecord(messageEvent.partial) ? messageEvent.partial : null;
		const content = partial && Array.isArray(partial.content) ? partial.content[index] : null;
		if (!isToolCall(content) || content.name !== "write_expected_output") return;
		this.observeArguments(content.arguments);
	}

	resetAttempt(): void {
		this.states.clear();
	}

	private observeArguments(args: Record<string, unknown>): void {
		for (const write of partialWrites(args)) {
			const contract = this.outputs.get(write.path);
			if (!contract || !streamable(contract.previewMode)) continue;
			this.observeContent(contract, write.content);
		}
	}

	private observeContent(contract: PreviewOutputContract, content: string): void {
		const previous = this.states.get(contract.path) ?? { content: "", revision: 1 };
		if (content === previous.content) return;
		const extendsPrevious = content.startsWith(previous.content);
		const revision = extendsPrevious ? previous.revision : previous.revision + 1;
		const delta = extendsPrevious ? content.slice(previous.content.length) : "";
		this.states.set(contract.path, { content, revision });
		if (extendsPrevious && delta) {
			this.emit("artifact.preview.delta", previewPayload(contract, revision, {
				delta,
				characters: content.length,
			}));
			return;
		}
		this.emit("artifact.preview.snapshot", previewPayload(contract, revision, {
			content,
			characters: content.length,
			replace: true,
		}));
	}
}

export function previewOutputContracts(context: TaskContext): PreviewOutputContract[] {
	return context.agentOwnedOutputs.map((output) => ({
		...output,
		previewMode: previewMode(output, context.agentRole),
	}));
}

export function previewMode(output: OutputContract, agentRole = ""): OutputPreviewMode {
	const format = output.format.toLowerCase();
	const kind = output.kind.toLowerCase();
	const path = output.path.toLowerCase();
	const role = agentRole.toLowerCase();
	if (kind.includes("completion") || path.endsWith(".agent_completion.json")) return "hidden";
	if (format === "json" || format === "yaml" || format === "yml") return "semantic_on_commit";
	if (kind.includes("prose") || role.includes("writing") || /(?:prose|candidate|drafts\/scenes)/.test(path)) {
		return "prose_stream";
	}
	if (format === "markdown" || path.endsWith(".md")) return "markdown_stream";
	if (format === "text" || path.endsWith(".txt")) return "markdown_stream";
	return "metadata_only";
}

export function partialWrites(args: Record<string, unknown>): Array<{ path: string; content: string }> {
	const result: Array<{ path: string; content: string }> = [];
	if (typeof args.path === "string" && typeof args.content === "string") {
		result.push({ path: normalizePath(args.path), content: args.content });
	}
	if (Array.isArray(args.outputs)) {
		for (const item of args.outputs) {
			if (!isRecord(item) || typeof item.path !== "string" || typeof item.content !== "string") continue;
			result.push({ path: normalizePath(item.path), content: item.content });
		}
	}
	return result;
}

function previewPayload(
	contract: PreviewOutputContract,
	revision: number,
	data: Record<string, unknown>,
): Record<string, unknown> {
	return {
		path: contract.path,
		kind: contract.kind,
		format: contract.format,
		preview_mode: contract.previewMode,
		identity: "streaming_preview",
		revision,
		...data,
	};
}

function streamable(mode: OutputPreviewMode): boolean {
	return mode === "prose_stream" || mode === "markdown_stream";
}

function isToolCall(value: unknown): value is { name: string; arguments: Record<string, unknown> } {
	return isRecord(value)
		&& value.type === "toolCall"
		&& typeof value.name === "string"
		&& isRecord(value.arguments);
}

function integerValue(value: unknown): number {
	return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : 0;
}

function normalizePath(value: string): string {
	return value.trim().replace(/\\/g, "/").replace(/^\.\//, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
