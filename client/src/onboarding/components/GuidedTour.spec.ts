import { afterEach, describe, expect, it } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h, KeepAlive, ref } from "vue";
import GuidedTour from "./GuidedTour.vue";

afterEach(() => { document.body.innerHTML = ""; });
describe("cached workspace guides", () => {
  it("hides its teleported dialog while its owning workspace is inert or deactivated", async () => {
    const visible = ref(true);
    const target = document.createElement("div");
    target.dataset.tourId = "archive-test";
    document.body.append(target);
    const source = defineComponent({ setup: () => () => h(GuidedTour, {
      active: true, steps: [{ targetId: "archive-test", title: "档案引导", eyebrow: "作品资产", body: "说明" }],
    }) });
    const wrapper = mount(defineComponent({ setup: () => () =>
      h(KeepAlive, null, { default: () => visible.value ? h(source) : null }),
    }), { attachTo: document.body });
    await flushPromises();
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
    target.setAttribute("inert", "");
    await flushPromises();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    target.removeAttribute("inert");
    await flushPromises();
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
    visible.value = false;
    await flushPromises();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    visible.value = true;
    await flushPromises();
    expect(document.querySelector('[role="dialog"]')).not.toBeNull();
    wrapper.unmount();
  });
});
