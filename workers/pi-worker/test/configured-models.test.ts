import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { configuredModels, parseConfiguredProviders } from "../src/configured-models.ts";
import { ReadOnlyJsonCredentialStore } from "../src/credential-store.ts";

const directories: string[] = [];
afterEach(async () => { for (const directory of directories.splice(0)) await rm(directory, { recursive: true, force: true }); });
const definition = () => ({ providers: { discovery: {
	api: "openai-completions", baseUrl: "https://example.test/v1", models: [{
		id: "fixed-model", contextWindow: 262144, maxTokens: 32768, reasoning: false,
		cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, samplingParams: { thinking_mode: false },
	}],
} } });

describe("configured SDK model catalog", () => {
	it("retains built-in providers without a custom file", async () => {
		const directory = await mkdtemp(join(tmpdir(), "arcvellum-models-")); directories.push(directory);
		const authPath = join(directory, "auth.json");
		const models = await configuredModels(new ReadOnlyJsonCredentialStore(authPath), authPath);
		expect(models.getModel("deepseek", "deepseek-v4-flash")).toBeDefined();
	});
	it("loads a configured model and resolves only the stored provider credential", async () => {
		const directory = await mkdtemp(join(tmpdir(), "arcvellum-models-")); directories.push(directory);
		const authPath = join(directory, "auth.json");
		await writeFile(join(directory, "models.json"), JSON.stringify(definition()));
		await writeFile(authPath, JSON.stringify({ discovery: { type: "api_key", key: "test-credential" } }));
		const models = await configuredModels(new ReadOnlyJsonCredentialStore(authPath), authPath);
		const model = models.getModel("discovery", "fixed-model")!;
		expect(model.baseUrl).toBe("https://example.test/v1");
		expect(model.samplingParams).toEqual({ thinking_mode: false });
		expect((await models.getAuth(model))?.auth.apiKey).toBe("test-credential");
	});
	it("does not silently fall back from invalid definitions", () => {
		const config = definition(); config.providers.discovery.models[0].maxTokens = 300000;
		expect(() => parseConfiguredProviders(config)).toThrow("exceeds");
	});
	it("rejects credential-bearing endpoints and credentials in the catalog", () => {
		const config = definition(); config.providers.discovery.baseUrl = "https://key@example.test/v1";
		expect(() => parseConfiguredProviders(config)).toThrow("baseUrl");
		const secret = { ...definition().providers.discovery, apiKey: "test-credential" };
		expect(() => parseConfiguredProviders({ providers: { discovery: secret } })).toThrow("auth.json");
	});
});
