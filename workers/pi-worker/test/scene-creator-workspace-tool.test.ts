import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { sceneCreatorV2Envelope } from "../src/conversation.ts";
import { createSceneArchiveTool, sceneScratchOperation, workArchiveOperation } from "../src/scene-creator-workspace-tool.ts";

const roots: string[] = [];
afterEach(async () => { for (const root of roots.splice(0)) await rm(root, { recursive: true, force: true }); });

describe("scene creator v2 work boundaries", () => {
	it("accepts a scoped v2 envelope and rejects incomplete roots", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-creator-"));
		roots.push(root);
		const envelope = { schema: "arcvellum/scene-creator/v2", system_prompt: "identity",
			material_root: join(root, "materials"), archive_root: join(root, "work"),
			scratch_root: join(root, "scratch"), prompt: "scene" };
		expect(sceneCreatorV2Envelope(JSON.stringify(envelope))?.archiveRoot).toBe(join(root, "work"));
		expect(() => sceneCreatorV2Envelope(JSON.stringify({ ...envelope, archive_root: "../escape" }))).toThrow();
	});

	it("reads archive in pages while scratch writes stay outside it", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-creator-"));
		roots.push(root);
		const archive = join(root, "work");
		const scratch = join(root, "scratch");
		await mkdir(join(archive, "characters"), { recursive: true });
		await writeFile(join(archive, "project.yaml"), "title: rain\n");
		await writeFile(join(archive, "characters", "qing.md"), "name: Qing\nsecret: letter\n");
		const listed = await workArchiveOperation(archive, { action: "list" });
		expect(JSON.stringify(listed)).toContain("characters/qing.md");
		const found = await workArchiveOperation(archive, { action: "search", query: "letter" });
		expect(JSON.stringify(found)).toContain("qing.md");
		const read = await workArchiveOperation(archive, { action: "read", path: "characters/qing.md", start_line: 2, end_line: 2 });
		expect(read.content).toBe("secret: letter\n");
		const delivered = await createSceneArchiveTool(archive, () => {}).execute("read", {
			action: "read", path: "characters/qing.md", start_line: 2, end_line: 2,
		});
		const receipt = (delivered.details as { archive_receipt: Record<string, unknown> }).archive_receipt;
		expect(receipt).toMatchObject({ path: "characters/qing.md", start_line: 2, end_line: 2, complete: true, file_sha256: read.file_sha256 });
		expect(receipt.content_sha256).toMatch(/^[a-f0-9]{64}$/);
		expect(receipt).not.toHaveProperty("content");
		await expect(workArchiveOperation(archive, { action: "read", path: "../outside.txt" })).rejects.toThrow();
		await sceneScratchOperation(scratch, { action: "write", path: "chapter/note.md", content: "keep mystery" });
		expect((await sceneScratchOperation(scratch, { action: "read", path: "chapter/note.md" })).content).toBe("keep mystery");
		expect(await readFile(join(archive, "characters", "qing.md"), "utf8")).toContain("secret: letter");
		await expect(sceneScratchOperation(scratch, { action: "write", path: "../work/project.yaml", content: "changed" })).rejects.toThrow();
	});
});
