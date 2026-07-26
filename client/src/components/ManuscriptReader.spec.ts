import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";
import { flushPromises, mount } from "@vue/test-utils";
import ManuscriptReader from "@/components/ManuscriptReader.vue";
import { useReaderNavigationStore } from "@/stores/readerNavigation";

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

  it("opens the exact unit requested by the Orrery and publishes the visible unit", async () => {
    const navigation = useReaderNavigationStore();
    navigation.request("scene_0002");
    const wrapper = mount(ManuscriptReader, {
      props: {
        mode: "reading",
        items: [
          { id: "scene_0001", title: "第一场", body: "第一场正文。" },
          { id: "scene_0002", title: "第二场", body: "第二场正文。" },
        ],
      },
    });
    await flushPromises();

    expect(wrapper.get(".reader-title-block h2").text()).toBe("第二场");
    expect(navigation.activeUnitId).toBe("scene_0002");
  });
});
