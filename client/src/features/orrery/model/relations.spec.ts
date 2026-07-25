import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  RELATION_FAMILIES,
  RELATION_FOCUS_STATES,
  RELATION_LOD_MODES,
  parseRelationVisibilityProfile,
  type RelationVisibilityProfile,
} from "@/features/orrery/model/relations";

interface SharedFixture {
  families: string[];
  lod_modes: string[];
  focus_states: string[];
  sample: RelationVisibilityProfile;
}

const fixturePath = resolve(process.cwd(), "contracts/fixtures/relation_visibility_profile.v1.json");
const fixture = JSON.parse(readFileSync(fixturePath, "utf-8")) as SharedFixture;

describe("RelationVisibilityProfile", () => {
  it("keeps enum values and parser aligned with the shared fixture", () => {
    expect([...RELATION_FAMILIES]).toEqual(fixture.families);
    expect([...RELATION_LOD_MODES]).toEqual(fixture.lod_modes);
    expect([...RELATION_FOCUS_STATES]).toEqual(fixture.focus_states);
    expect(parseRelationVisibilityProfile(fixture.sample)).toEqual(fixture.sample);
  });

  it("normalizes malformed counts without inventing a relation family", () => {
    const profile = parseRelationVisibilityProfile({ edge_count: -4, focus_weight: "bad" });
    expect(profile.family).toBe("context-association");
    expect(profile.edge_count).toBe(0);
    expect(profile.focus_weight).toBe(0);
  });
});
