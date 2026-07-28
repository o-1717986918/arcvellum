import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StyleSourceWorkshop from "./StyleSourceWorkshop.vue";

describe("StyleSourceWorkshop", () => {
  it("keeps the create action available and explains missing requirements", async () => {
    const wrapper = mount(StyleSourceWorkshop, {
      props: {
        authors: [],
        selectedAuthorId: "",
        selectedWorkId: "",
        busy: false,
      },
    });

    const button = wrapper.find("button.primary");
    expect(button.attributes("disabled")).toBeUndefined();
    await wrapper.find("form").trigger("submit");
    expect(wrapper.text()).toContain("请填写作者名称");

    await wrapper.find('input[placeholder="例如：某位公版作家"]').setValue("鲁迅");
    await wrapper.find("textarea").setValue("该作品属于公版文本，可用于文风分析。");
    expect((wrapper.find('input[placeholder="例如：classic-author"]').element as HTMLInputElement).value).toMatch(/^author-[a-z0-9]{7}$/);
    await wrapper.find("form").trigger("submit");

    expect(wrapper.emitted("createAuthor")?.[0]?.[0]).toMatchObject({
      name: "鲁迅",
      rights_mode: "public-domain",
    });
    wrapper.unmount();
  });
});
