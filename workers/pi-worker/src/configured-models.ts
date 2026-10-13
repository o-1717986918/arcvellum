import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { createProvider, envApiKeyAuth, type CredentialStore, type Model, type MutableModels } from "@earendil-works/pi-ai";
import { builtinModels } from "@earendil-works/pi-ai/providers/all";
import { openAICompletionsApi } from "@earendil-works/pi-ai/api/openai-completions.lazy";

/** Extend the existing Pi SDK catalog; credentials remain in its read-only store. */
export async function configuredModels(credentials: CredentialStore, authPath: string): Promise<MutableModels> {
	const catalog = builtinModels({ credentials });
	let source: string;
	try {
		source = await readFile(join(dirname(authPath), "models.json"), "utf8");
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === "ENOENT") return catalog;
		throw error;
	}
	const providers = parseConfiguredProviders(JSON.parse(source));
	for (const provider of providers) {
		if (catalog.getProvider(provider.id)) throw new Error(`Custom model provider conflicts with built-in catalog: ${provider.id}`);
		catalog.setProvider(createProvider({
			...provider,
			auth: { apiKey: envApiKeyAuth(`${provider.name} API key`, []) },
			api: openAICompletionsApi(),
		}));
	}
	return catalog;
}

export function parseConfiguredProviders(value: unknown) {
	if (!record(value) || !record(value.providers)) throw new Error("Pi models.json requires a providers object");
	return Object.entries(value.providers).map(([id, definition]) => {
		if (!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(id) || !record(definition)) throw new Error("Invalid custom model provider");
		if (definition.api !== "openai-completions") throw new Error(`Unsupported configured model API: ${id}`);
		if ("apiKey" in definition || "headers" in definition) throw new Error("Use auth.json for custom provider credentials");
		const baseUrl = endpoint(definition.baseUrl);
		if (!Array.isArray(definition.models) || !definition.models.length) throw new Error(`Custom provider has no models: ${id}`);
		const models = definition.models.map((entry: unknown) => configuredModel(id, baseUrl, entry));
		if (new Set(models.map(model => model.id)).size !== models.length) throw new Error(`Duplicate configured model: ${id}`);
		return { id, name: typeof definition.name === "string" ? definition.name : id, baseUrl, models };
	});
}

function configuredModel(provider: string, baseUrl: string, entry: unknown): Model<"openai-completions"> {
	if (!record(entry) || typeof entry.id !== "string" || !entry.id.trim() || /\s/.test(entry.id)) throw new Error("Invalid configured model ID");
	if ("apiKey" in entry || "headers" in entry) throw new Error("Model definitions cannot contain credentials");
	const contextWindow = positiveInteger(entry.contextWindow, "contextWindow");
	const maxTokens = positiveInteger(entry.maxTokens, "maxTokens");
	if (maxTokens > contextWindow) throw new Error("Configured maxTokens exceeds contextWindow");
	if (typeof entry.reasoning !== "boolean") throw new Error("Configured model must declare reasoning support");
	const input = entry.input ?? ["text"];
	if (!Array.isArray(input) || !input.length || input.some(item => item !== "text" && item !== "image")) throw new Error("Invalid model input modalities");
	if (!record(entry.cost) || ["input", "output", "cacheRead", "cacheWrite"].some(key =>
		typeof entry.cost[key] !== "number" || !Number.isFinite(entry.cost[key]) || entry.cost[key] < 0)) throw new Error("Invalid configured model cost");
	if (entry.compat !== undefined && !record(entry.compat)) throw new Error("Invalid model compatibility settings");
	if (entry.samplingParams !== undefined && !record(entry.samplingParams)) throw new Error("Invalid model request parameters");
	return {
		id: entry.id, name: typeof entry.name === "string" ? entry.name : entry.id,
		provider, baseUrl, api: "openai-completions", reasoning: entry.reasoning,
		input, contextWindow, maxTokens, cost: entry.cost as Model<"openai-completions">["cost"],
		...(entry.compat === undefined ? {} : { compat: entry.compat }),
		...(entry.samplingParams === undefined ? {} : { samplingParams: entry.samplingParams }),
	};
}

function endpoint(value: unknown): string {
	if (typeof value !== "string") throw new Error("Configured model baseUrl is required");
	const url = new URL(value);
	if (!/^https?:$/.test(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error("Invalid model baseUrl");
	return value.replace(/\/$/, "");
}

function positiveInteger(value: unknown, field: string): number {
	if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 1) throw new Error(`Invalid model ${field}`);
	return value;
}

function record(value: unknown): value is Record<string, any> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
