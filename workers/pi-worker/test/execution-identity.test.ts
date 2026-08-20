import { describe, expect, it } from "vitest";
import { executionIdentities } from "../src/execution-identity.ts";
import {
	PiArtifactExecutor,
	PiCreativeWorker,
	PiReviewWorker,
	workerExecutionStrategy,
} from "../src/worker-strategy.ts";

const context = {
	taskId: "scene-0004-compose",
	projectId: "project-1234567890abcdef",
	agentRole: "main-creative-agent",
	promptAsset: { resolved_id: "scene-compose", version: "3" },
};
const profile = { version: "1" as const, digest: "profile-digest" };

describe("worker execution identity", () => {
	it("keeps cache identity stable while isolating every run", () => {
		const first = executionIdentities(context, profile, "deepseek/model", "task", "nonce-one");
		const second = executionIdentities(context, profile, "deepseek/model", "task", "nonce-two");
		expect(first.promptCacheKey).toBe(second.promptCacheKey);
		expect(first.runSessionId).not.toBe(second.runSessionId);
	});

	it("invalidates cache identity across project, role, model, profile, or prompt revision", () => {
		const baseline = executionIdentities(context, profile, "deepseek/model", "task", "same").promptCacheKey;
		const variants = [
			{ ...context, projectId: "project-other" },
			{ ...context, agentRole: "main-review-agent" },
			{ ...context, promptAsset: { ...context.promptAsset, version: "4" } },
		];
		for (const variant of variants) {
			expect(executionIdentities(variant, profile, "deepseek/model", "task", "same").promptCacheKey).not.toBe(baseline);
		}
		expect(executionIdentities(context, profile, "other/model", "task", "same").promptCacheKey).not.toBe(baseline);
		expect(executionIdentities(context, { ...profile, digest: "new" }, "deepseek/model", "task", "same").promptCacheKey).not.toBe(baseline);
	});

	it("does not share a legacy project cache across tasks", () => {
		const first = executionIdentities({ ...context, projectId: "project-legacy" }, profile, "deepseek/model", "task", "one");
		const second = executionIdentities({ ...context, projectId: "project-legacy", taskId: "other" }, profile, "deepseek/model", "task", "two");
		expect(first.promptCacheKey).not.toBe(second.promptCacheKey);
	});
});

describe("Pi execution strategies", () => {
	it("selects role-specific immutable values without duplicating route logic", () => {
		expect(workerExecutionStrategy("main-creative-agent")).toBe(PiCreativeWorker);
		expect(workerExecutionStrategy("main-review-agent")).toBe(PiReviewWorker);
		expect(workerExecutionStrategy("canon-auditor")).toBe(PiReviewWorker);
		expect(workerExecutionStrategy("asset-agent")).toBe(PiArtifactExecutor);
		expect(PiCreativeWorker.noProgressTurnLimit).toBeGreaterThan(PiReviewWorker.noProgressTurnLimit);
	});
});
