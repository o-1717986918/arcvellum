import { describe, expect, it } from "vitest";
import { inheritedTextChange } from "./revisionComparison";
import type { ArtifactRevision, ArtifactRevisionSummary } from "./types";

function summary(revision_id: string, digest: string, identity: ArtifactRevisionSummary["identity"] = "candidate_written"): ArtifactRevisionSummary {
  return { revision_id, artifact_id: "scene", event_id: revision_id, at: "2026-09-25T00:00:00Z", identity, digest, characters: 10, finding_refs: [] };
}

describe("revision comparison", () => {
  it("finds the text-changing draft inherited by an unchanged formal promotion", () => {
    const revisions = [summary("initial", "a"), summary("revised", "b"), summary("reviewed", "b"), summary("promoted", "b", "promoted")];
    const promoted: ArtifactRevision = { ...revisions[3], content: "修订正文", diff: "" };
    expect(inheritedTextChange(revisions, promoted)?.revision_id).toBe("revised");
  });

  it("does not replace a real promotion change or a different selected version", () => {
    const revisions = [summary("initial", "a"), summary("promoted", "b", "promoted")];
    expect(inheritedTextChange(revisions, { ...revisions[1], content: "新正文", diff: "+新正文" })).toBeNull();
    expect(inheritedTextChange(revisions, { ...revisions[1], content: "新正文", diff: "" })).toBeNull();
    expect(inheritedTextChange(revisions, { ...revisions[0], content: "初稿", diff: "" })).toBeNull();
  });
});
