import { lstat, mkdir, readFile, rename, unlink, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, posix, relative, resolve, sep, win32 } from "node:path";
import { randomUUID } from "node:crypto";

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
	return readFile(target, "utf8");
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
