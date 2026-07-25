import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  CHARACTER_REFERENCE_RESOLUTIONS,
  buildCharacterThreadGroups,
  parseCharacterReference,
  type CharacterReference,
} from "@/features/orrery/model/characters";
import type { SpatialNarrativeNode } from "@/types/spatial";

interface SharedFixture {
  resolutions: string[];
  cases: Array<{ name: string; payload: CharacterReference }>;
}

const fixturePath = resolve(process.cwd(), "contracts/fixtures/character_reference.v1.json");
const fixture = JSON.parse(readFileSync(fixturePath, "utf-8")) as SharedFixture;

describe("CharacterReference", () => {
  it("keeps TypeScript resolution values and payload parsing aligned with Python", () => {
    expect([...CHARACTER_REFERENCE_RESOLUTIONS]).toEqual(fixture.resolutions);
    for (const entry of fixture.cases) expect(parseCharacterReference(entry.payload)).toEqual(entry.payload);
  });

  it("groups the current chapter, the remaining book and unresolved mentions", () => {
    const references = [
      fixture.cases[0].payload,
      {
        ...fixture.cases[0].payload,
        reference_id: "wen",
        node_id: "character:wen",
        character_id: "wen",
        display_name: "闻舟",
        scene_ids: ["scene_0003"],
        chapter_ids: ["chapter_0002"],
      },
      fixture.cases[1].payload,
    ];
    const nodes = references.map((reference, index) => ({
      node_id: reference.node_id,
      type: "character",
      label: reference.display_name,
      order: index,
    })) as SpatialNarrativeNode[];
    const groups = buildCharacterThreadGroups(references, nodes, "chapter_0001");
    expect(groups.map((group) => group.id)).toEqual(["current", "book", "unresolved"]);
    expect(groups[0].items[0].node.node_id).toBe("character:lin");
    expect(groups[1].items[0].node.node_id).toBe("character:wen");
  });
});
