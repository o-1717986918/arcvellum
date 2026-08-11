import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { atomicWriteAuthorizedFile, normalizeRelativePath } from "../src/path-policy.ts";

const roots: string[] = [];

afterEach(async () => {
	await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })));
});

describe("path policy", () => {
	it.each(["../secret", "a/../../secret", "C:\\secret", "/secret", ""])('rejects unsafe path "%s"', (value) => {
		expect(() => normalizeRelativePath(value)).toThrow();
	});

	it("writes an authorized relative output atomically", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-worker-path-"));
		roots.push(root);
		await atomicWriteAuthorizedFile(root, "reviews/result.json", "{}\n");
		expect(await readFile(join(root, "reviews", "result.json"), "utf8")).toBe("{}\n");
	});
});
