import { createHash } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { readSceneMaterial, readSceneMaterials } from "../src/scene-material-tool.ts";

const roots: string[] = [];
afterEach(async () => { for (const root of roots.splice(0)) await rm(root, { recursive: true, force: true }); });

describe("scene creator material permission", () => {
	it("reads multiple full candidates in one call and rejects unknown IDs", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-material-"));
		roots.push(root);
		const entries = [];
		for (const id of ["event:1", "environment:1"]) {
			const file = createHash("sha256").update(id).digest("hex").slice(0, 24) + ".json";
			await writeFile(join(root, file), JSON.stringify({ schema: "arcvellum/scene-material/v1", candidate_id: id,
				content: { text: "长过程".repeat(3000) } }));
			entries.push({ candidate_id: id, file });
		}
		await writeFile(join(root, "index.json"), JSON.stringify({ schema: "arcvellum/scene-material-library/v1", entries }));
		const result = JSON.parse(await readSceneMaterials(root, ["event:1", "environment:1"]));
		expect(result.materials).toHaveLength(2);
		expect(result.materials[1].content.text).toBe("长过程".repeat(3000));
		await expect(readSceneMaterials(root, ["event:1", "missing"])).rejects.toThrow("unknown scene material ID");
		await expect(readSceneMaterials(root, Array(9).fill("event:1"))).rejects.toThrow("one to eight");
	});
	it("explains that an empty library needs a creator request", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-material-"));
		roots.push(root);
		await writeFile(join(root, "index.json"), JSON.stringify({
			schema: "arcvellum/scene-material-library/v1", entries: [],
		}));
		const empty = JSON.parse(await readSceneMaterial(root));
		expect(empty.status).toBe("empty_before_request");
		expect(empty.message).toContain("material_requests");
	});

	it("lists metadata and reads only indexed candidates", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-material-"));
		roots.push(root);
		const id = "d1:1";
		const file = createHash("sha256").update(id).digest("hex").slice(0, 24) + ".json";
		const body = { schema: "arcvellum/scene-material/v1", candidate_id: id, kind: "event-narration",
			content: { text: "昨夜信被取走。" } };
		await writeFile(join(root, file), JSON.stringify(body));
		await writeFile(join(root, "index.json"), JSON.stringify({ schema: "arcvellum/scene-material-library/v1",
			entries: [{ candidate_id: id, kind: "event-narration", target: "昨夜取信", purpose: "改变读者认知",
				scene_moment: "此刻", file }] }));
		expect(await readSceneMaterial(root)).toContain("event-narration");
		expect(await readSceneMaterial(root)).not.toContain("昨夜信被取走");
		expect(await readSceneMaterial(root, id)).toContain("昨夜信被取走");
		await expect(readSceneMaterial(root, "../other")).rejects.toThrow("unknown scene material ID");
	});

	it("rejects paths supplied by a tampered index", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-material-"));
		roots.push(root);
		await writeFile(join(root, "index.json"), JSON.stringify({ schema: "arcvellum/scene-material-library/v1",
			entries: [{ candidate_id: "d1:1", file: "../outside.json" }] }));
		await expect(readSceneMaterial(root, "d1:1")).rejects.toThrow("unknown scene material ID");
	});

	it("reads a scene context larger than the old 8,000-character limit", async () => {
		const root = await mkdtemp(join(tmpdir(), "arcvellum-material-"));
		roots.push(root);
		const id = "scene-context";
		const file = createHash("sha256").update(id).digest("hex").slice(0, 24) + ".json";
		await writeFile(join(root, file), JSON.stringify({ schema: "arcvellum/scene-material/v1",
			candidate_id: id, content: { director_turns: [{ director_note: "线索".repeat(5_000) }] } }));
		await writeFile(join(root, "index.json"), JSON.stringify({ schema: "arcvellum/scene-material-library/v1",
			entries: [{ candidate_id: id, kind: "scene-context", target: "", purpose: "", scene_moment: "", file }] }));
		expect(await readSceneMaterial(root, id)).toContain("线索".repeat(5_000));
	});
});
