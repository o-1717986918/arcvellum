import { readFile, realpath } from "node:fs/promises";
import { dirname, isAbsolute, join } from "node:path";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { Type } from "@earendil-works/pi-ai";
import { ActiveContextReads } from "./active-context-reads.ts";
import { projectMaterialRead } from "./material-read-projection.ts";

interface MaterialEntry {
	candidate_id: string;
	kind: string;
	target: string;
	purpose: string;
	scene_moment: string;
	basis?: "confirmed" | "attributed" | "proposed";
	file: string;
}

/** The scene creator can list and read only files named by its transaction index. */
export function createSceneMaterialTool(root: string, onRead: () => void, delivered = new ActiveContextReads()): AgentTool {
	if (!isAbsolute(root)) throw new Error("scene material root must be absolute");
	return {
		name: "read_scene_material",
		label: "Read Scene Material",
    description: "List candidate IDs, or read full literary source by candidate_id or candidate_ids. Repeated metadata is omitted; source_field_spans identify exact fields in content.text using JavaScript UTF-16 offsets. A batch supports comparison.",
		parameters: Type.Object({ candidate_id: Type.Optional(Type.String()),
			candidate_ids: Type.Optional(Type.Array(Type.String(), { minItems: 1, maxItems: 8 })) }),
		executionMode: "sequential",
		execute: async (_id, params) => {
			onRead();
			const request = params as { candidate_id?: string; candidate_ids?: string[] };
			const candidateId = String(request.candidate_id || "").trim();
			if (candidateId && request.candidate_ids) throw new Error("choose candidate_id or candidate_ids");
			const text = request.candidate_ids ? await readSceneMaterials(root, request.candidate_ids) : await readSceneMaterial(root, candidateId);
			const value = JSON.parse(text);
			const projected = Array.isArray(value.materials) ? { ...value, materials: value.materials.map((row: Record<string, unknown>) =>
				delivered.receipt(row, _id)) } : Array.isArray(value) ? value : delivered.receipt(value, _id);
			return { content: [{ type: "text", text: JSON.stringify(projected) }], details: { candidate_id: candidateId, candidate_ids: request.candidate_ids } };
		},
	};
}

export async function readSceneMaterials(root: string, candidateIds: string[]): Promise<string> {
	if (!Array.isArray(candidateIds) || candidateIds.length < 1 || candidateIds.length > 8
		|| candidateIds.some((id) => typeof id !== "string" || !id.trim())) throw new Error("select one to eight candidate IDs");
	const ids = [...new Set(candidateIds)];
	const materials = await Promise.all(ids.map(async (id) => JSON.parse(await readSceneMaterial(root, id))));
	const text = JSON.stringify({ materials, complete: true });
	if (text.length > 64_000) throw new Error("selected materials exceed the batch context budget; select fewer IDs");
    return text;
}

export async function readSceneMaterial(root: string, candidateId = ""): Promise<string> {
	if (!isAbsolute(root)) throw new Error("scene material root must be absolute");
	let resolvedRoot: string;
	try { resolvedRoot = await realpath(root); }
	catch {
		if (candidateId) throw new Error("scene material library is empty");
		return emptyMaterialIndex();
	}
	const indexPath = await authorizedPath(resolvedRoot, "index.json");
	const index = JSON.parse(await readFile(indexPath, "utf8")) as { schema?: string; entries?: MaterialEntry[] };
	if (index.schema !== "arcvellum/scene-material-library/v1" || !Array.isArray(index.entries)) {
		throw new Error("scene material index is invalid");
	}
	if (!candidateId) {
		if (index.entries.length === 0) return emptyMaterialIndex();
		return JSON.stringify(index.entries.map(({ file: _file, ...metadata }) => metadata));
	}
	const entry = index.entries.find((item) => item.candidate_id === candidateId);
	if (!entry || !/^[a-f0-9]{24}\.json$/.test(entry.file)) throw new Error("unknown scene material ID");
	const filePath = await authorizedPath(resolvedRoot, entry.file);
	const text = await readFile(filePath, "utf8");
	// A source material packet may reach 20,000 characters before it is split and
	// pretty-printed into files. Keep a bounded read that can still return it.
	if (text.length > 64_000) throw new Error("scene material file exceeds read limit");
	const material = JSON.parse(text) as { candidate_id?: string; schema?: string };
	if (material.schema !== "arcvellum/scene-material/v1" || material.candidate_id !== candidateId) {
		throw new Error("scene material file does not match its index");
	}
	return JSON.stringify(projectMaterialRead(material as Record<string, unknown>));
}

function emptyMaterialIndex(): string {
	return JSON.stringify({
		status: "empty_before_request",
		entries: [],
		message: "本场尚未生成候选。请按作者意图在最终 JSON 中提交 material_requests；read_scene_material 只能读取生成后的文件。空目录不是 agent 不可用的证据。",
	});
}

async function authorizedPath(root: string, filename: string): Promise<string> {
	const resolved = await realpath(join(root, filename));
	if (dirname(resolved) !== root) throw new Error("scene material path escapes its library");
	return resolved;
}
