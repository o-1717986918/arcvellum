import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { useOrreryExplorationStore } from "@/stores/orreryExploration";

describe("orrery exploration store", () => {
  beforeEach(() => {
    window.localStorage.clear();
    setActivePinia(createPinia());
  });

  it("keeps project-scoped view bookmarks without writing project files", () => {
    const store = useOrreryExplorationStore();
    const item = store.save({
      projectRoot: "C:/works/one", label: "高潮前", level: "chapter", focus: "chapter_0003",
      grammar: "spine", timeCursor: 18, timeWindow: 3, heatLens: "tension", nodeId: "chapter:chapter_0003",
    });
    store.save({
      projectRoot: "C:/works/two", label: "开场", level: "book", focus: "",
      grammar: "braid", timeCursor: 0, timeWindow: 3, heatLens: "", nodeId: "",
    });
    expect(store.forProject("C:/works/one")).toHaveLength(1);
    store.remove(item.id);
    expect(store.forProject("C:/works/one")).toHaveLength(0);
  });
});
