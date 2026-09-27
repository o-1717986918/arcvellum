import { createHash } from "node:crypto";
import mainCreativeAgentProfile from "../profiles/main-creative-agent.md?raw";
import incrementalRepairProfile from "../profiles/incremental-repair.md?raw";
import genericWorkerProfile from "../profiles/generic-role.md?raw";

export const WORKER_PROFILE_SCHEMA = "arcvellum/pi-worker-profile/v1";
export const WORKER_PROFILE_VERSION = "2";

export interface WorkerProfile {
	schema: typeof WORKER_PROFILE_SCHEMA;
	version: typeof WORKER_PROFILE_VERSION;
	role: string;
	digest: string;
	systemPrompt: string;
}

/**
 * Stable, skill-like Worker bootstrap. Project evidence and current task
 * contracts deliberately do not belong here: they have independent digests
 * and invalidation rules in Studio's Prompt Program.
 */
export function workerProfile(agentRole: string, mode: "task" | "repair" = "task"): WorkerProfile {
	const systemPrompt = mode === "repair"
		? incrementalRepairProfile.trim()
		: systemPromptForRole(agentRole);
	const digest = createHash("sha256")
		.update(`${WORKER_PROFILE_SCHEMA}\0${WORKER_PROFILE_VERSION}\0${agentRole}\0${mode}\0${systemPrompt}`)
		.digest("hex");
	return {
		schema: WORKER_PROFILE_SCHEMA,
		version: WORKER_PROFILE_VERSION,
		role: agentRole,
		digest,
		systemPrompt,
	};
}

function systemPromptForRole(agentRole: string): string {
    if (agentRole === "main-creative-agent") {
        return mainCreativeAgentProfile.trim();
    }
	return genericWorkerProfile.trim().replace("[[ARCVELLUM_PROMPT_0]]", agentRole);
}
