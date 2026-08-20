import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import AdvisorFloatingShell from "./AdvisorFloatingShell.vue";

function pointer(type: string, values: Record<string, number>): Event {
  const event = new Event(type);
  Object.defineProperties(event, Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, { value }]),
  ));
  return event;
}

describe("AdvisorFloatingShell", () => {
  beforeEach(() => {
    localStorage.clear();
    Object.defineProperty(window, "innerWidth", { value: 1440, configurable: true });
    Object.defineProperty(window, "innerHeight", { value: 900, configurable: true });
    vi.stubGlobal("matchMedia", () => ({ matches: false, addListener: vi.fn(), removeListener: vi.fn() }));
  });

  it("opens from the orb and preserves the phone-like default dimensions", async () => {
    const wrapper = mount(AdvisorFloatingShell, { props: { open: false, unreadCount: 12 } });
    expect(wrapper.get(".advisor-unread").text()).toBe("9+");
    await wrapper.get(".advisor-orb").trigger("click");
    expect(wrapper.emitted("update:open")?.at(-1)).toEqual([true]);

    await wrapper.setProps({ open: true });
    expect(wrapper.get(".advisor-dock").attributes("style")).toContain("width: 390px");
    expect(wrapper.get(".advisor-dock").attributes("style")).toContain("height: 680px");
  });

  it("persists a dragged dock without changing its dimensions", async () => {
    const wrapper = mount(AdvisorFloatingShell, {
      props: { open: true },
      slots: { header: "<span>顾问标题</span>" },
    });
    const header = wrapper.get(".advisor-dock-header");
    await header.trigger("pointerdown", { button: 0, clientX: 10, clientY: 20 });
    window.dispatchEvent(pointer("pointermove", { clientX: 90, clientY: 120 }));
    window.dispatchEvent(pointer("pointerup", { clientX: 90, clientY: 120 }));
    await wrapper.vm.$nextTick();

    expect(localStorage.getItem("arcvellum.advisorDockPosition")).toBe('{"left":80,"top":100}');
    const style = wrapper.get(".advisor-dock").attributes("style");
    expect(style).toContain("width: 390px");
    expect(style).toContain("height: 680px");
  });
});
