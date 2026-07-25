import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StructuredAssetEditor from "./StructuredAssetEditor.vue";
import type { ArchiveStructuredDocument } from "../types";

describe("StructuredAssetEditor", () => {
  it("emits only fields changed through the registry contract", async () => {
    const wrapper = mount(StructuredAssetEditor, {
      props: { document: characterDocument() },
    });

    const name = wrapper.find(".archive-form-field input[type='text']");
    await name.setValue("林汐");
    await wrapper.find(".archive-structured-toolbar button").trigger("click");

    expect(wrapper.emitted("apply")?.[0]).toEqual([{ name: "林汐" }]);
    expect(wrapper.text()).toContain("仅修改 Registry 允许的字段");
  });

  it("provides safe Markdown preview and stable table row controls", async () => {
    const document: ArchiveStructuredDocument = {
      asset_id: "scene:scene_0001",
      editor_kind: "form",
      document_format: "yaml",
      source_revision: "sha256:scene",
      fields: [
        {
          name: "scene_goal",
          label: "场景目标",
          kind: "markdown",
          section: "戏剧任务",
          required: false,
          defined: true,
          value: "**揭开**线索",
        },
        {
          name: "reader_experience",
          label: "读者体验",
          kind: "table",
          section: "读者体验",
          required: false,
          defined: true,
          value: [{ question: "灯是谁点亮的？" }],
        },
      ],
    };
    const wrapper = mount(StructuredAssetEditor, { props: { document } });

    await wrapper.findAll(".archive-markdown-editor nav button")[1].trigger("click");

    expect(wrapper.find(".archive-markdown-preview strong").text()).toBe("揭开");
    expect(wrapper.text()).toContain("条目 1");
    expect(wrapper.text()).toContain("新增条目");
  });
});

function characterDocument(): ArchiveStructuredDocument {
  return {
    asset_id: "character:lin",
    editor_kind: "form",
    document_format: "yaml",
    source_revision: "sha256:character",
    fields: [
      {
        name: "name",
        label: "姓名",
        kind: "text",
        section: "身份",
        required: true,
        defined: true,
        value: "林澈",
      },
      {
        name: "importance",
        label: "叙事级别",
        kind: "choice",
        section: "身份",
        required: true,
        defined: true,
        value: "major",
        options: ["major", "secondary", "minor"],
      },
    ],
  };
}
