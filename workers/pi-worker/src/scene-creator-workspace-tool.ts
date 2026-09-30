import { createHash, randomUUID } from "node:crypto";
import { lstat, mkdir, readFile, readdir, realpath, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import type { AgentTool } from "@earendil-works/pi-agent-core";
import { Type } from "@earendil-works/pi-ai";

const privateNames = new Set([".git", ".env", ".codex", ".agent", "auth.json", "secrets.json"]);
const decoder = new TextDecoder("utf-8", { fatal: true });

function archiveStatus(path: string): string {
	if (path.startsWith("canon/")) return "canon";
	if (path.startsWith("drafts/scenes/")) return "scene_prose";
	if (path.startsWith("workflow/scene_deltas/") || path === "workflow/continuity/current.json") return "mixed_continuity";
	if (path === "workflow/studio/user_directions.md") return "user_direction";
	if (path.startsWith("characters/")) return "character_archive";
	if (path.startsWith("plot/") || path.startsWith("scenes/")) return "planning";
	return "archive_reference";
}

function parts(value: string, allowEmpty = false): string[] {
	const normalized = value.replaceAll("\\", "/").trim();
	if (!normalized && allowEmpty) return [];
	const result = normalized.split("/");
	if (!normalized || isAbsolute(normalized) || normalized.includes(":") || result.some((part) =>
		!part || part === "." || part === ".." || part.startsWith(".") || privateNames.has(part.toLowerCase()))) {
		throw new Error("path is outside the scene creator workspace");
	}
	return result;
}

async function safePath(root: string, path: string, allowEmpty = false): Promise<string> {
	if (!isAbsolute(root)) throw new Error("scene creator workspace root must be absolute");
	const rootPath = await realpath(root);
	let cursor = rootPath;
	for (const part of parts(path, allowEmpty)) {
		cursor = join(cursor, part);
		try {
			if ((await lstat(cursor)).isSymbolicLink()) throw new Error("symbolic links are unavailable");
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
		}
	}
	const inside = relative(rootPath, resolve(cursor));
	if (inside.startsWith(`..${sep}`) || inside === ".." || isAbsolute(inside)) throw new Error("workspace path escapes root");
	return cursor;
}

async function files(root: string): Promise<string[]> {
	const output: string[] = [];
	async function walk(directory: string, prefix: string): Promise<void> {
		for (const entry of await readdir(directory, { withFileTypes: true })) {
			if (entry.name.startsWith(".") || privateNames.has(entry.name.toLowerCase()) || entry.isSymbolicLink()) continue;
			const name = prefix ? `${prefix}/${entry.name}` : entry.name;
			if (entry.isDirectory()) await walk(join(directory, entry.name), name);
			else if (entry.isFile()) output.push(name);
		}
	}
	await walk(await realpath(root), "");
	return output.sort();
}

export async function workArchiveOperation(root: string, input: Record<string, unknown>): Promise<Record<string, unknown>> {
	const action = String(input.action || "");
	if (action === "list") {
		const prefix = String(input.path || "");
		parts(prefix, true);
		const all = (await files(root)).filter((name) => !prefix || name === prefix || name.startsWith(`${prefix.replace(/\/$/, "")}/`));
		const offset = Math.max(0, Number(input.offset || 0));
		return { entries: all.slice(offset, offset + 100).map((path) => ({ path, status: archiveStatus(path) })),
			next_offset: offset + 100 < all.length ? offset + 100 : null };
	}
	if (action === "search") {
		const query = String(input.query || "").trim().toLowerCase();
		if (!query || query.length > 200) throw new Error("archive search needs a short query");
		const found: { path: string; line: number; preview: string }[] = [];
		for (const name of await files(root)) {
			if (name.toLowerCase().includes(query)) found.push({ path: name, line: 0, preview: name });
			const path = await safePath(root, name);
			if ((await stat(path)).size > 8_000_000) continue;
			let body: string;
			try { body = decoder.decode(await readFile(path)); } catch { continue; }
			for (const [index, line] of body.split(/\r?\n/).entries()) {
				if (line.toLowerCase().includes(query)) found.push({ path: name, line: index + 1, preview: line.slice(0, 200) });
				if (found.length >= 5000) break;
			}
			if (found.length >= 5000) break;
		}
		const offset = Math.max(0, Number(input.offset || 0));
		return { matches: found.slice(offset, offset + 50), next_offset: offset + 50 < found.length ? offset + 50 : null };
	}
	if (action === "read") {
		const name = String(input.path || "");
		const path = await safePath(root, name);
		if ((await stat(path)).size > 8_000_000) throw new Error("archive entry exceeds readable file limit");
		const body = decoder.decode(await readFile(path));
		const lines = body.split(/(?<=\n)/);
		const start = Number(input.start_line || 1);
		const end = input.end_line === undefined ? lines.length : Number(input.end_line);
		if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) throw new Error("invalid line range");
		const selected = lines.slice(start - 1, end).join("");
		const offset = Math.max(0, Number(input.offset || 0));
		const content = selected.slice(offset, offset + 16_000);
		return { path: name, status: archiveStatus(name), start_line: start, end_line: Math.min(end, lines.length), content,
			complete: offset + content.length >= selected.length,
			next_offset: offset + content.length < selected.length ? offset + content.length : null,
			file_sha256: createHash("sha256").update(body).digest("hex") };
	}
	throw new Error("archive action must be list, search, or read");
}

export async function sceneScratchOperation(root: string, input: Record<string, unknown>): Promise<Record<string, unknown>> {
	if (!isAbsolute(root)) throw new Error("scene scratch root must be absolute");
	await mkdir(root, { recursive: true });
	const action = String(input.action || "");
	if (action === "list") {
		const prefix = String(input.path || "");
		parts(prefix, true);
		const all = await files(root);
		return { entries: all.filter((name) => !prefix || name === prefix || name.startsWith(`${prefix}/`)).slice(0, 500) };
	}
	const path = await safePath(root, String(input.path || ""));
	if (action === "read") {
		if ((await stat(path)).size > 1_000_000) throw new Error("scratch file exceeds read limit");
		return { path: input.path, content: decoder.decode(await readFile(path)) };
	}
	if (action === "write") {
		const content = String(input.content ?? "");
		if (Buffer.byteLength(content) > 1_000_000) throw new Error("scratch file exceeds write limit");
		await mkdir(dirname(path), { recursive: true });
		const temporary = join(dirname(path), `.scratch-${randomUUID()}`);
		try { await writeFile(temporary, content, "utf8"); await rename(temporary, path); }
		finally { await rm(temporary, { force: true }); }
		return { path: input.path, written: true };
	}
	if (action === "move") {
		const destination = await safePath(root, String(input.destination || ""));
		await mkdir(dirname(destination), { recursive: true });
		try { await lstat(destination); throw new Error("scratch destination exists"); }
		catch (error) { if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error; }
		await rename(path, destination);
		return { path: input.path, destination: input.destination, moved: true };
	}
	if (action === "delete") {
		await rm(path);
		return { path: input.path, deleted: true };
	}
	throw new Error("scratch action must be list, read, write, move, or delete");
}

export function createSceneArchiveTool(root: string, onCall: () => void): AgentTool {
	return {
		name: "work_archive", label: "Read Work Archive",
		description: "List, search, or read work archive files. Read-only; use offset to continue a long result.",
		parameters: Type.Object({
			action: Type.Union([Type.Literal("list"), Type.Literal("search"), Type.Literal("read")]),
			path: Type.Optional(Type.String()), query: Type.Optional(Type.String()),
			start_line: Type.Optional(Type.Integer({ minimum: 1 })),
			end_line: Type.Optional(Type.Integer({ minimum: 1 })),
			offset: Type.Optional(Type.Integer({ minimum: 0 })),
		}),
		executionMode: "sequential",
		execute: async (_id, params) => {
			onCall();
			const result = await workArchiveOperation(root, params as Record<string, unknown>);
			return { content: [{ type: "text", text: JSON.stringify(result) }], details: { action: (params as Record<string, unknown>).action } };
		},
	};
}

export function createSceneScratchTool(root: string, onCall: () => void): AgentTool {
	return {
		name: "creator_scratch", label: "Scene Creator Scratch",
		description: "List, read, write, move, or delete files in the creator's persistent work-only scratch area.",
		parameters: Type.Object({
			action: Type.Union([Type.Literal("list"), Type.Literal("read"), Type.Literal("write"), Type.Literal("move"), Type.Literal("delete")]),
			path: Type.Optional(Type.String()), content: Type.Optional(Type.String()),
			destination: Type.Optional(Type.String()),
		}),
		executionMode: "sequential",
		execute: async (_id, params) => {
			onCall();
			const result = await sceneScratchOperation(root, params as Record<string, unknown>);
			return { content: [{ type: "text", text: JSON.stringify(result) }], details: { action: (params as Record<string, unknown>).action } };
		},
	};
}
