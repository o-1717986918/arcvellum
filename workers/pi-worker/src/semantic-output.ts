import type { TaskContext, ValidationIssue } from "./contracts.ts";

export function validateSemanticOutput(
	context: TaskContext,
	path: string,
	value: unknown,
): ValidationIssue[] {
	const contract = context.semanticOutputContract;
	if (!isRecord(contract) || stringValue(contract.path) !== path || !isRecord(value)) return [];

	const modelOwned = new Set(stringList(contract.model_owned_fields));
	const required = stringList(contract.required_fields).filter((field) => modelOwned.has(field));
	const fieldTypes = recordValue(contract.field_types);
	const issues: ValidationIssue[] = [];

	for (const field of required) {
		if (!Object.hasOwn(value, field)) {
			issues.push(issue(path, "semantic_missing_field", `model-owned field is missing: ${field}`));
			continue;
		}
		const expected = stringValue(fieldTypes[field]);
		if (expected && !matchesType(value[field], expected)) {
			issues.push(issue(
				path,
				"semantic_type_mismatch",
				`model-owned field ${field} must be ${expected}`,
			));
		}
	}

	issues.push(...validateObjectShapes(path, value, recordValue(contract.object_shapes), modelOwned));
	return issues;
}

function validateObjectShapes(
	path: string,
	value: Record<string, unknown>,
	shapes: Record<string, unknown>,
	modelOwned: Set<string>,
): ValidationIssue[] {
	const issues: ValidationIssue[] = [];
	for (const [shapeKey, rawShape] of Object.entries(shapes)) {
		const arrayShape = shapeKey.endsWith("[]");
		const field = arrayShape ? shapeKey.slice(0, -2) : shapeKey;
		if (!modelOwned.has(field) || !Object.hasOwn(value, field) || !isRecord(rawShape)) continue;
		if (arrayShape) {
			if (!Array.isArray(value[field])) continue;
			value[field].forEach((item, index) => {
				if (!isRecord(item)) {
					issues.push(issue(path, "semantic_shape_mismatch", `${field}[${index}] must be an object`));
					return;
				}
				issues.push(...requiredShapeIssues(path, `${field}[${index}]`, item, rawShape));
			});
			continue;
		}
		if (isRecord(value[field])) {
			issues.push(...requiredShapeIssues(path, field, value[field], rawShape));
		}
	}
	return issues;
}

function requiredShapeIssues(
	path: string,
	prefix: string,
	value: Record<string, unknown>,
	shape: Record<string, unknown>,
): ValidationIssue[] {
	const issues: ValidationIssue[] = [];
	for (const [field, rawDescriptor] of Object.entries(shape)) {
		const descriptor = stringValue(rawDescriptor);
		if (descriptor.toLowerCase().includes("optional")) continue;
		if (!Object.hasOwn(value, field)) {
			issues.push(issue(path, "semantic_missing_field", `model-owned field is missing: ${prefix}.${field}`));
			continue;
		}
		if (descriptor && hasKnownType(descriptor) && !matchesType(value[field], descriptor)) {
			issues.push(issue(
				path,
				"semantic_type_mismatch",
				`model-owned field ${prefix}.${field} must be ${descriptor}`,
			));
		}
	}
	return issues;
}

function hasKnownType(descriptor: string): boolean {
	return /^(list|dict|object|str|string|bool|boolean|int|integer|number)\b/i.test(descriptor.trim());
}

function matchesType(value: unknown, descriptor: string): boolean {
	const expected = descriptor.trim().toLowerCase().split(/[;|\s]/, 1)[0];
	if (expected === "list") return Array.isArray(value);
	if (expected === "dict" || expected === "object") return isRecord(value);
	if (expected === "str" || expected === "string") return typeof value === "string";
	if (expected === "bool" || expected === "boolean") return typeof value === "boolean";
	if (expected === "int" || expected === "integer") return Number.isInteger(value);
	if (expected === "number") return typeof value === "number" && Number.isFinite(value);
	return true;
}

function issue(path: string, code: string, message: string): ValidationIssue {
	return { path, code, message };
}

function stringList(value: unknown): string[] {
	return Array.isArray(value) ? value.map(stringValue).filter(Boolean) : [];
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
