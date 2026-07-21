import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import OnboardingTour from "./OnboardingTour.vue";

describe("OnboardingTour", () => {
  it("adapts to project state and can finish the visual guide", async () => {
    const wrapper = mount(OnboardingTour, { props: { active: true, hasProject: true } });
    expect(document.body.textContent).toContain("作品已经就位");
    expect(document.body.textContent).toContain("1 / 5");
    for (let index = 0; index < 4; index += 1) {
      await document.querySelector<HTMLButtonElement>(".tour-next")?.click();
      await wrapper.vm.$nextTick();
    }
    expect(document.body.textContent).toContain("开始创作");
    await document.querySelector<HTMLButtonElement>(".tour-next")?.click();
    expect(wrapper.emitted("complete")).toHaveLength(1);
    wrapper.unmount();
  });
});
