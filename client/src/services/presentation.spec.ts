import { describe, expect, it } from "vitest";
import { displayValue, manuscriptItems, sectionEntries } from "./presentation";

describe("human-facing project presentation", () => {
  it("prefers completed prose and does not expose workflow records", () => {
    const items = manuscriptItems({
      completed_prose: {
        items: [{ id: "scene_0001", title: "雨停以后", body: "正文" }],
      },
      sections: {
        drafts: [{ id: "candidate", status: "candidate", body: "候选" }],
        reviews: [{ id: "review", body: "审查" }],
      },
    });
    expect(items).toHaveLength(1);
    expect(items[0].title).toBe("雨停以后");
  });

  it("normalizes record sections into filterable entries", () => {
    const entries = sectionEntries({
      characters: [{ id: "lin", title: "林夏" }],
      world: [{ id: "harbor", title: "旧港" }],
    });
    expect(entries.map(([key]) => key)).toEqual(["characters", "world"]);
    expect(entries[0][1][0].title).toBe("林夏");
  });

  it("renders structured values as readable labels instead of JSON", () => {
    expect(displayValue({ title: "潮汐规则", path: "canon/world_rules.yaml" })).toBe("潮汐规则");
    expect(displayValue(["承诺", "代价"])).toBe("承诺、代价");
  });
});
