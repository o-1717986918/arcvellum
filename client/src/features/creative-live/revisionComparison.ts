import type { ArtifactRevision, ArtifactRevisionSummary } from "./types";

/** A promotion may repeat its preceding draft verbatim; show the change that produced that text. */
export function inheritedTextChange(
  revisions: ArtifactRevisionSummary[],
  selected: ArtifactRevision,
): ArtifactRevisionSummary | null {
  if (selected.identity !== "promoted" || selected.diff.trim() || !selected.digest) return null;
  const selectedIndex = revisions.findIndex((item) => item.revision_id === selected.revision_id);
  if (selectedIndex < 1 || revisions[selectedIndex - 1]?.digest !== selected.digest) return null;
  let firstMatching = selectedIndex - 1;
  while (firstMatching > 0 && revisions[firstMatching - 1]?.digest === selected.digest) firstMatching -= 1;
  return revisions[firstMatching] || null;
}
