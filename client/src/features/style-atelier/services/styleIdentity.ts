export function styleIdentity(label: string, prefix: "author" | "work" | "style"): string {
  const normalized = label
    .normalize("NFKD")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 54);
  if (normalized.length >= 2) return normalized;
  return `${prefix}-${stableLabelHash(label || prefix)}`;
}

function stableLabelHash(value: string): string {
  let hash = 2166136261;
  for (const character of value) {
    hash = Math.imul(hash ^ character.codePointAt(0)!, 16777619);
  }
  return (hash >>> 0).toString(36).padStart(7, "0").slice(0, 7);
}
