import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import NewConversationDialog from "./NewConversationDialog.vue";

const baseProject = {
  title: "潮线",
  work_type: "novel",
  target_length: 80_000,
  status: "drafting",
  genre: "悬疑",
  premise: "潮退后，旧港显露一条不存在的街。",
  direction_count: 1,
};

describe("NewConversationDialog", () => {
  it("adds stable metadata and a folder hint for same-titled works", () => {
    const wrapper = mount(NewConversationDialog, {
      props: {
        projects: [
          { ...baseProject, path: "C:/works/tide-a" },
          { ...baseProject, path: "C:/archive/tide-b", target_length: 120_000 },
        ],
      },
    });

    const metadata = wrapper.findAll(".pa-dialog-project-meta").map((item) => item.text());
    expect(metadata[0]).toContain("目标 80,000 字");
    expect(metadata[0]).toContain("tide-a");
    expect(metadata[1]).toContain("目标 120,000 字");
    expect(metadata[1]).toContain("tide-b");
  });

  it("emits the workspace event used by the parent for an empty library", async () => {
    const wrapper = mount(NewConversationDialog, { props: { projects: [] } });

    await wrapper.get(".pa-dialog-create").trigger("click");

    expect(wrapper.emitted("createProject")).toHaveLength(1);
  });
});
