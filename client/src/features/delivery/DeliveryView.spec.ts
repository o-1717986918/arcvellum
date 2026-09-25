import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it, vi } from "vitest";
import { useAppStore } from "@/stores/app";
import { deliveryClient } from "./services/deliveryClient";
import DeliveryView from "./DeliveryView.vue";

describe("partial delivery", () => {
  it("offers the current manuscript DOCX before the full book is ready", async () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const store = useAppStore();
    store.setCurrentProject("C:\\ArcVellum\\unfinished", false);
    store.projectProgress = { formal_chinese_content_chars: 500 } as typeof store.projectProgress;
    store.readerManifest = { unit_count: 1 } as typeof store.readerManifest;
    store.delivery = { ok: true, project_root: "C:\\ArcVellum\\unfinished", status: "partial", blockers: [], files: [] } as typeof store.delivery;
    vi.spyOn(store, "loadDelivery").mockResolvedValue(undefined);
    vi.spyOn(store, "loadProjectProgress").mockResolvedValue(undefined);
    vi.spyOn(store, "loadReaderManifest").mockResolvedValue(undefined);
    const snapshot = vi.spyOn(deliveryClient, "createSnapshot").mockResolvedValue({} as never);

    const wrapper = mount(DeliveryView, { global: { plugins: [pinia] } });
    const button = wrapper.findAll("button").find((item) => item.text().includes("导出当前稿 DOCX"));
    expect(button?.attributes("disabled")).toBeUndefined();
    await button?.trigger("click");
    await flushPromises();

    expect(snapshot).toHaveBeenCalledWith("C:\\ArcVellum\\unfinished");
    expect(wrapper.text()).toContain("只包含此刻已晋升的正文");
    wrapper.unmount();
    vi.restoreAllMocks();
  });
});
