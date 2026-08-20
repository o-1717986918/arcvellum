import { lstat, mkdir, readFile, readdir, rename, unlink, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, posix, relative, resolve, sep, win32 } from "node:path";
import { randomUUID } from "node:crypto";

const MAX_AUTHORIZED_SOURCE_BYTES = 4 * 1024 * 1024;
const MAX_DIRECTORY_MEMBERS = 500;

export function normalizeRelativePath(value: string): string {
	const replaced = value.trim().replaceAll("\\", "/");
	if (!replaced || isAbsolute(replaced) || win32.isAbsolute(replaced) || /^[A-Za-z]:/.test(replaced)) {
		throw new Error("path must be workspace-relative");
	}
	const normalized = posix.normalize(replaced);
	if (normalized === "." || normalized === ".." || normalized.startsWith("../") || normalized.includes("/../")) {
		throw new Error("path traversal is not allowed");
	}
	return normalized;
}

export async function readAuthorizedFile(root: string, relativePath: string): Promise<string> {
	const target = await resolveWorkspacePath(root, relativePath, false);
	const info = await lstat(target);
	if (!info.isFile() || info.isSymbolicLink()) throw new Error("authorized source must be a regular file");
	if (info.size > MAX_AUTHORIZED_SOURCE_BYTES) throw new Error("authorized source exceeds the bounded file limit");
	const data = await readFile(target);
	if (data.includes(0)) throw new Error("authorized source must be UTF-8 text");
	try {
		return new TextDecoder("utf-8", { fatal: true }).decode(data);
	} catch {
		throw new Error("authorized source must be UTF-8 text");
	}
}

export async function readAuthorizedSource(root: string, relativePath: string): Promise<string> {
	const target = await resolveWorkspacePath(root, relativePath, false);
	const info = await lstat(target);
	if (info.isSymbolicLink()) throw new Error("authorized source cannot be a symbolic link");
	if (info.isFile()) return readAuthorizedFile(root, relativePath);
	if (!info.isDirectory()) throw new Error("authorized source must be a regular file or directory");
	const members = await directoryMembers(root, relativePath, target);
	const listed = members.slice(0, MAX_DIRECTORY_MEMBERS);
	const lines = [
		`# Authorized directory evidence: ${relativePath}`,
		"Use the same evidence_id with member_path set to one exact file below.",
		`Discovered members: ${members.length}; listed: ${listed.length}; truncated: ${members.length > listed.length}`,
		"",
		...listed.map((item) => `- ${item}`),
	];
	return lines.join("\n") + "\n";
}

async function directoryMembers(root: string, relativeRoot: string, absoluteRoot: string): Promise<string[]> {
	const result: string[] = [];
	const pending = [absoluteRoot];
	while (pending.length > 0) {
		const directory = pending.pop();
		if (!directory) break;
		const entries = await readdir(directory, { withFileTypes: true });
		for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
			if (entry.isSymbolicLink()) throw new Error("authorized directory contains a symbolic link");
			const child = resolve(directory, entry.name);
			if (entry.isDirectory()) {
				pending.push(child);
				continue;
			}
			if (!entry.isFile()) continue;
			const relation = relative(resolve(root), child).split(sep).join("/");
			if (!relation || relation.startsWith("../")) throw new Error("authorized directory member escapes the workspace");
			result.push(relation);
			if (result.length > MAX_DIRECTORY_MEMBERS) return result.sort();
		}
	}
	return result.sort();
}

export async function atomicWriteAuthorizedFile(root: string, relativePath: string, content: string): Promise<void> {
	const target = await resolveWorkspacePath(root, relativePath, true);
	await mkdir(dirname(target), { recursive: true });
	await assertNoSymlinkBetween(root, dirname(target));
	const temporary = `${target}.arcvellum-${randomUUID()}.tmp`;
	try {
		await writeFile(temporary, content, "utf8");
		await rename(temporary, target);
	} catch (error) {
		await unlink(temporary).catch(() => undefined);
		throw error;
	}
}

export async function resolveWorkspacePath(root: string, relativePath: string, allowMissing: boolean): Promise<string> {
	const normalized = normalizeRelativePath(relativePath);
	const workspace = resolve(root);
	const target = resolve(workspace, ...normalized.split("/"));
	const relation = relative(workspace, target);
	if (!relation || relation.startsWith("..") || isAbsolute(relation)) {
		throw new Error("path escapes the workspace");
	}
	await assertNoSymlinkBetween(workspace, allowMissing ? dirname(target) : target);
	return target;
}

async function assertNoSymlinkBetween(root: string, target: string): Promise<void> {
	const workspace = resolve(root);
	const relation = relative(workspace, resolve(target));
	if (relation.startsWith("..") || isAbsolute(relation)) throw new Error("path escapes the workspace");
	let cursor = workspace;
	for (const segment of relation.split(sep).filter(Boolean)) {
		cursor = resolve(cursor, segment);
		try {
			const info = await lstat(cursor);
			if (info.isSymbolicLink()) throw new Error("symbolic links are not allowed in worker paths");
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code === "ENOENT") return;
			throw error;
		}
	}
}
