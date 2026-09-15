import { readFile } from "node:fs/promises";
import type { TaskContext, ValidationIssue } from "./contracts.ts";
import { resolveWorkspacePath } from "./path-policy.ts";

const CHINESE_CONTENT_RE = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3001-\u303f\ufe10-\ufe1f\ufe30-\ufe4f\uff01-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65\u2018-\u201d\u2014\u2026\u00b7\u{20000}-\u{2ebef}]/gu;
const PROSE_HEADING_RE = /^##\s*(?:正文草稿|正文候选|修订正文候选)\s*$/m;
const INTERNAL_HEADING_RE = /^\s{0,3}#{1,6}\s*(?:状态变化|状态变化候选|世界状态变化|角色状态变化|场景状态变化|世界线变化|写回|写回清单|写回候选|写回候选汇总|状态写回|自检|创作说明|工作流程|审查|审查状态|canon|上下文|提示词|Prompt|需要人工确认|新增事实候选|人物状态变化|关系变化|伏笔变化|新角色|新角色候选|新角色候选登记)\b.*$/im;

export async function validateLiteraryOutput(
	context: TaskContext,
	workspace: string,
	path: string,
	text: string,
	parsed?: unknown,
): Promise<ValidationIssue[]> {
	const issues: ValidationIssue[] = [];
	if (isProseOutput(context, path)) {
		const count = countChineseContentChars(deliverableBody(text));
		const minimum = positiveInteger(context.wordCount.minimum);
		const maximum = positiveInteger(context.wordCount.maximum);
		if (minimum > 0 && count < minimum) {
			const gap = minimum - count;
			issues.push({
				path,
				code: "prose_below_word_count_minimum",
				message: `cleaned body has ${count} Chinese content chars, below min_chinese_chars=${minimum}; add at least ${gap} meaningful Chinese content chars to the current complete body and do not replace it with a shorter version`,
			});
		}
		if (maximum > 0 && count > maximum) {
			issues.push({
				path,
				code: "prose_above_word_count_maximum",
				message: `cleaned body has ${count} Chinese content chars, above max_chinese_chars=${maximum}; reduce the current complete body by at least ${count - maximum} Chinese content chars before rewriting other outputs`,
			});
		}
	}
	if (path === stringValue(context.semanticOutputContract.path) && isRecord(parsed)) {
		issues.push(...await exactRevisionEvidenceIssues(context, workspace, path, parsed));
	}
	return issues;
}

export function proseLengthMeasure(
	context: TaskContext,
	path: string,
	text: string,
): { count: number; minimum: number; maximum: number } | null {
	if (!isProseOutput(context, path)) return null;
	return {
		count: countChineseContentChars(deliverableBody(text)),
		minimum: positiveInteger(context.wordCount.minimum),
		maximum: positiveInteger(context.wordCount.maximum),
	};
}

function isProseOutput(context: TaskContext, path: string): boolean {
	if (positiveInteger(context.wordCount.minimum) === 0 && positiveInteger(context.wordCount.maximum) === 0) return false;
	const binding = recordValue(context.semanticOutputContract.source_binding);
	const boundCandidate = stringValue(binding.candidate_path);
	if (boundCandidate) return path === boundCandidate;
	if (!path.endsWith(".md") || path.includes("agent_tasks") || path.includes("_report")) return false;
	return (
		context.currentState === "candidate-generation-provenance"
		|| context.currentState === "generation-agent-task"
		|| path.includes("drafts/candidates/")
		|| /drafts\/revisions\/[^/]+_revision(?:_\d+)?\.md$/.test(path)
	);
}

async function exactRevisionEvidenceIssues(
	context: TaskContext,
	workspace: string,
	manifestPath: string,
	payload: Record<string, unknown>,
): Promise<ValidationIssue[]> {
	const binding = recordValue(context.semanticOutputContract.source_binding);
	const sourcePath = stringValue(binding.source_path);
	const candidatePath = stringValue(binding.candidate_path);
	if (!sourcePath || !candidatePath || !Array.isArray(payload.anti_evasion_rows)) return [];
	const [sourceText, candidateText] = await Promise.all([
		readWorkspaceText(workspace, sourcePath),
		readWorkspaceText(workspace, candidatePath),
	]);
	if (sourceText === null || candidateText === null) return [];
	const sourceBody = deliverableBody(sourceText);
	const candidateBody = deliverableBody(candidateText);
	const issues: ValidationIssue[] = [];
	payload.anti_evasion_rows.forEach((rawRow, index) => {
		if (!isRecord(rawRow)) return;
		const sourceExcerpt = stringValue(rawRow.source_excerpt);
		const revisedExcerpt = stringValue(rawRow.revised_excerpt);
		if (sourceExcerpt && !sourceBody.includes(sourceExcerpt)) {
			issues.push({
				path: manifestPath,
				code: "revision_source_excerpt_mismatch",
				message: `anti_evasion_rows[${index}].source_excerpt is not present in the exact source body; remove unsupported rows when no exact source evidence exists`,
			});
		}
		if (revisedExcerpt && !candidateBody.includes(revisedExcerpt)) {
			issues.push({
				path: manifestPath,
				code: "revision_candidate_excerpt_mismatch",
				message: `anti_evasion_rows[${index}].revised_excerpt is not present in the revised candidate body`,
			});
		}
	});
	return issues;
}

async function readWorkspaceText(workspace: string, path: string): Promise<string | null> {
	try {
		return await readFile(await resolveWorkspacePath(workspace, path, false), "utf8");
	} catch {
		return null;
	}
}

function deliverableBody(text: string): string {
	let body = text.replace(/<!--[^]*?-->/g, "").trim();
	const heading = PROSE_HEADING_RE.exec(body);
	if (heading?.index !== undefined) body = body.slice(heading.index + heading[0].length).trim();
	const internal = INTERNAL_HEADING_RE.exec(body);
	if (internal?.index !== undefined) body = body.slice(0, internal.index).trim();
	return body;
}

function countChineseContentChars(text: string): number {
	return [...text.matchAll(CHINESE_CONTENT_RE)].length;
}

function positiveInteger(value: unknown): number {
	return typeof value === "number" && Number.isInteger(value) && value > 0 ? value : 0;
}

function stringValue(value: unknown): string {
	return typeof value === "string" ? value.trim() : "";
}

function recordValue(value: unknown): Record<string, unknown> {
	return isRecord(value) ? value : {};
}

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === "object" && value !== null && !Array.isArray(value);
}
