import { createHash, randomUUID } from "node:crypto";
import type { TaskContext } from "./contracts.ts";
import type { WorkerProfile } from "./worker-profile.ts";

export interface ExecutionIdentities {
	runSessionId: string;
	promptCacheKey: string;
}

export function executionIdentities(
	context: Pick<TaskContext, "taskId" | "projectId" | "agentRole" | "promptAsset">,
	profile: Pick<WorkerProfile, "digest" | "version">,
	model: string,
	mode: "task" | "repair",
	nonce: string = randomUUID(),
): ExecutionIdentities {
	const projectScope = context.projectId === "project-legacy"
		? `${context.projectId}:${context.taskId}`
		: context.projectId;
	return {
		runSessionId: `arcvellum-run-${digest(`${context.taskId}\0${mode}\0${model}\0${nonce}`)}`,
		promptCacheKey: `arcvellum-cache-${digest([
			projectScope,
			context.agentRole,
			model,
			profile.version,
			profile.digest,
			stringField(context.promptAsset, "resolved_id"),
			stringField(context.promptAsset, "version"),
		].join("\0"))}`,
	};
}

function stringField(value: Record<string, unknown>, key: string): string {
	const item = value[key];
	return typeof item === "string" ? item : "";
}

function digest(value: string): string {
	return createHash("sha256").update(value).digest("hex").slice(0, 24);
}
