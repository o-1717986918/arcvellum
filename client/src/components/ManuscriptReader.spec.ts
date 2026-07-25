import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ManuscriptReader from "@/components/ManuscriptReader.vue";

describe("ManuscriptReader", () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
  });

  it("renders a real prose preview and delegates all controlled state changes", async () => {
    const wrapper = mount(ManuscriptReader, {
      props: {
        mode: "peek",
        items: [{
          id: "scene_0001",
          title: "潮声抵达之前",
          body: "她先听见门外的潮声。\n第二段仍在远处。",
          chapter_id: "chapter_0001",
          chinese_content_chars: 24,
        }],
      },
    });
    await flushPromises();
    expect(wrapper.get(".reader-peek-body").text()).toContain("她先听见门外的潮声");
    await wrapper.get('button[title="展开正文阅读器"]').trigger("click");
    expect(wrapper.emitted("modeChange")?.at(-1)).toEqual(["reading"]);

    await wrapper.setProps({ mode: "reading" });
    expect(wrapper.find(".reader-layout").exists()).toBe(true);
    await wrapper.get('button[title="进入沉浸阅读"]').trigger("click");
    expect(wrapper.emitted("modeChange")?.at(-1)).toEqual(["immersive"]);

    await wrapper.setProps({ mode: "immersive" });
    expect(wrapper.classes()).toContain("reader-state-immersive");
    await wrapper.get('button[title="返回星仪阅读窗"]').trigger("click");
    expect(wrapper.emitted("modeChange")?.at(-1)).toEqual(["reading"]);
  });
});
