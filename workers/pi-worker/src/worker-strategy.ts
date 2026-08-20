export interface PiWorkerExecutionStrategy {
	id: "artifact" | "creative" | "review";
	noProgressTurnLimit: number;
	semanticJudgment: boolean;
}

export const PiArtifactExecutor: Readonly<PiWorkerExecutionStrategy> = Object.freeze({
	id: "artifact",
	noProgressTurnLimit: 2,
	semanticJudgment: false,
});

export const PiCreativeWorker: Readonly<PiWorkerExecutionStrategy> = Object.freeze({
	id: "creative",
	noProgressTurnLimit: 3,
	semanticJudgment: true,
});

export const PiReviewWorker: Readonly<PiWorkerExecutionStrategy> = Object.freeze({
	id: "review",
	noProgressTurnLimit: 2,
	semanticJudgment: true,
});

export function workerExecutionStrategy(agentRole: string): Readonly<PiWorkerExecutionStrategy> {
	const normalized = agentRole.trim().toLowerCase();
	if (normalized === "main-creative-agent") return PiCreativeWorker;
	if (normalized.includes("review") || normalized.includes("auditor")) return PiReviewWorker;
	return PiArtifactExecutor;
}
