import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  NARRATIVE_FOCUS_LEVELS,
  parseNarrativeFocusScope,
  type NarrativeFocusScope,
} from "@/features/orrery/model/focusScope";

interface SharedFixture {
  levels: string[];
  cases: Array<{ name: string; payload: NarrativeFocusScope }>;
}

const fixturePath = resolve(process.cwd(), "contracts/fixtures/narrative_focus_scope.v1.json");
const fixture = JSON.parse(readFileSync(fixturePath, "utf-8")) as SharedFixture;

describe("NarrativeFocusScope", () => {
  it("keeps TypeScript enum and payload parsing aligned with the shared fixture", () => {
    expect([...NARRATIVE_FOCUS_LEVELS]).toEqual(fixture.levels);
    for (const entry of fixture.cases) {
      expect(parseNarrativeFocusScope(entry.payload)).toEqual(entry.payload);
    }
  });

  it("accepts the legacy focus field without inventing scope members", () => {
    expect(parseNarrativeFocusScope({ level: "scene", focus: "scene_0007" })).toEqual({
      level: "scene",
      focus_id: "scene_0007",
      chapter_ids: [],
      scene_ids: [],
      character_ids: [],
      anchor_node_ids: [],
      context_node_ids: [],
    });
  });
});
