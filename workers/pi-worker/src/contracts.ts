export interface OutputContract {
	path: string;
	kind: string;
	format: string;
	schemaName: string;
}

export interface TaskContext {
	schema: string;
	taskId: string;
	projectId: string;
	route: string;
	currentState: string;
	agentRole: string;
	executionPolicy: string;
	expectedOutputs: string[];
	agentOwnedOutputs: OutputContract[];
	exactOnDemand: string[];
	excluded: string[];
	readablePaths: string[];
	writablePaths: string[];
	hardConstraints: string[];
	styleConstraints: string[];
	validationGates: string[];
	wordCount: Record<string, number>;
	semanticPassCondition: Record<string, unknown>;
	promptAsset: Record<string, unknown>;
	promptAccess: Record<string, unknown>;
	evidenceIndex: Record<string, string>;
	maxResultChars: number;
	raw: Record<string, unknown>;
}

export interface WorkerOptions {
	workspace: string;
	model: string;
	authPath: string;
	thinking: "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";
	maxTurns: number;
	maxToolCalls: number;
	maxRepairs: number;
	allowedStates: string[];
	reasoningBudget: ReasoningBudget;
	providerReliability: ProviderReliabilityPolicy;
	mode: "task" | "repair";
	repairTargets: string[];
}

export interface ProviderReliabilityPolicy {
	firstEventTimeoutMs: number;
	interEventTimeoutMs: number;
	totalTimeoutMs: number;
	maxRetries: number;
	circuitFailureThreshold: number;
	circuitCooldownMs: number;
}

export type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh" | "max";

export interface ReasoningBudget {
	enabled: boolean;
	initialLevel: ThinkingLevel;
	maximumLevel: ThinkingLevel;
	perRequestTokens: number;
	totalTokens: number;
	maxProviderRequests: number;
	maxEscalations: number;
	overBudgetAction: "validate_then_stop" | "stop";
}

export interface ReasoningBudgetReceipt {
	requested: Record<string, unknown>;
	effective_level: ThinkingLevel;
	provider_support: "supported" | "partial" | "unsupported" | "unknown";
	actual_tokens: number | null;
	actual_characters: number;
	provider_requests: number;
	escalations: Array<{ from: ThinkingLevel; to: ThinkingLevel; reason: string }>;
	stop_reason: string;
}

export interface ValidationIssue {
	path: string;
	code: string;
	message: string;
}

export interface ValidationResult {
	passed: boolean;
	issues: ValidationIssue[];
}

export interface WorkerState {
	completed: boolean;
	blocked: boolean;
	blockerReason: string;
	turns: number;
	toolCalls: number;
	repairRequests: number;
	taskContextReads: number;
	reasoningCharacters: number;
	reasoningTokens: number;
	reasoningTokensReported: boolean;
	providerRequests: number;
	reasoningEscalations: Array<{ from: ThinkingLevel; to: ThinkingLevel; reason: string }>;
	reasoningStopReason: string;
	textCharacters: number;
	readPaths: Set<string>;
	writtenPaths: Set<string>;
	lastValidation: ValidationResult;
	lastToolError: { tool: string; reason: string } | null;
	progressDigests: string[];
}

export type RuntimeEventSink = (event: string, data?: Record<string, unknown>) => void;
