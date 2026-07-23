import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.fn();

vi.mock("@/services/api", () => ({
  api: apiMock,
  query: (values: Record<string, string>) => new URLSearchParams(values).toString(),
}));

describe("human choice store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMock.mockReset();
  });

  it("removes a consumed choice immediately and keeps a stable receipt", async () => {
    const choice = {
      choice_id: "choice.branch.abc",
      route: "scene-development",
      decision_type: "branch_selection",
      target: { scene_id: "scene_0001" },
      options: [{ id: "branch-a", label: "走向灯塔" }],
    };
    let loadCount = 0;
    apiMock.mockImplementation(async (path: string) => {
      if (path.startsWith("/workflow/current-choice")) {
        loadCount += 1;
        return { choices: loadCount === 1 ? [choice] : [] };
      }
      if (path === "/workflow/human-choice") {
        return {
          ok: true,
          schema: "arcvellum/human-choice-receipt/v0.2",
          receipt_id: "receipt.stable",
          choice_id: choice.choice_id,
          selected: "branch-a",
          recorded: true,
          materialized: "branches/scene_0001/branch_selection.md",
          materialized_ok: true,
          consumed: true,
          effect: { summary: "剧情分支已经进入正式流程。" },
          state_before: {},
          state_after: {},
        };
      }
      throw new Error(`unexpected path: ${path}`);
    });

    const { useHumanChoicesStore } = await import("./humanChoices");
    const store = useHumanChoicesStore();
    await store.load("C:\\ArcVellum\\novel");
    store.open(choice);
    const receipt = await store.submit("C:\\ArcVellum\\novel", choice.options[0]);

    expect(receipt.receipt_id).toBe("receipt.stable");
    expect(store.choices).toEqual([]);
    expect(store.completed).toBe(true);
    expect(store.message).toContain("正式流程");
  });
});
