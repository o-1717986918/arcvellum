import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AssetCreationPanel from "./AssetCreationPanel.vue";

describe("AssetCreationPanel", () => {
  it("materializes a registered template and requires an owner-reviewed preview", async () => {
    const wrapper = mount(AssetCreationPanel, {
      props: {
        options: [
          {
            asset_type: "character",
            template: 'character_id: "__ASSET_ID__"\nname: ""\nimportance: secondary\n',
            available: true,
          },
        ],
        preview: null,
        busy: false,
      },
    });

    await wrapper.find('input[placeholder="例如 new_character"]').setValue("mei");
    const source = wrapper.find(".archive-create-source textarea");
    expect((source.element as HTMLTextAreaElement).value).toContain('character_id: "mei"');
    await source.setValue('character_id: "mei"\nname: "梅汐"\nimportance: secondary\n');
    await wrapper.find(".archive-create-reason textarea").setValue("作者创建新的正式人物资产。");
    await wrapper.find('.archive-owner-check input[type="checkbox"]').setValue(true);

    const check = wrapper.findAll("footer button")[0];
    expect(check.attributes("disabled")).toBeUndefined();
    await check.trigger("click");

    const event = wrapper.emitted("preview");
    expect(event).toHaveLength(1);
    expect(event?.[0]?.[0]).toMatchObject({
      asset_type: "character",
      local_id: "mei",
      semantic_review: "waived",
    });
  });
});
