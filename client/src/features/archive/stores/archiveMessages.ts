export function expectedImpactNames(impact: Record<string, unknown>): string[] {
  const values = impact.stale_categories;
  if (Array.isArray(values)) return values.map(String);
  const categories = impact.categories;
  return Array.isArray(categories) ? categories.map(String) : [];
}

export function archiveErrorMessage(cause: unknown, fallback: string): string {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}
