import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import WorkspaceDock from "./WorkspaceDock.vue";

describe("WorkspaceDock", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("keeps the delivery center reachable before the release gates pass", async () => {
    const wrapper = mount(WorkspaceDock, {
      props: { pendingChoices: 0, deliveryReady: false },
    });
    const delivery = wrapper.find('button[title="查看交付准备状态与正式文件"]');

    expect(delivery.exists()).toBe(true);
    expect(delivery.attributes("disabled")).toBeUndefined();
    expect(delivery.classes()).not.toContain("delivery-ready");

    await delivery.trigger("click");
    expect(wrapper.emitted("open")?.[0]).toEqual(["delivery"]);
  });

  it("lights the same entry when formal delivery is ready", () => {
    const wrapper = mount(WorkspaceDock, {
      props: { pendingChoices: 0, deliveryReady: true },
    });

    expect(wrapper.find('button[title="查看交付准备状态与正式文件"]').classes()).toContain("delivery-ready");
  });
});
