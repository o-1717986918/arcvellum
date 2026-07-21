import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { nextTick } from "vue";
import { describe, expect, it, vi } from "vitest";
import ImmersiveConsole from "./ImmersiveConsole.vue";

describe("ImmersiveConsole", () => {
  it("keeps route health and decisions available together", async () => {
    const choice = {
      choice_id: "choice-1",
      decision_type: "branch_selection",
      title: "选择剧情分支",
      summary: "决定下一场的代价。",
    };
    const wrapper = mount(ImmersiveConsole, {
      props: {
        open: ["health", "decisions"],
        choices: [choice],
        prose: [],
        routeAudits: [{ route: "scene-development", blocking_count: 0, gate_count: 12 }],
      },
    });

    expect(wrapper.text()).toContain("场景创作");
    expect(wrapper.text()).toContain("12 项");
    expect(wrapper.text()).toContain("选择剧情分支");
    expect(wrapper.findAll('.immersive-console-panel[data-edge="right"]')).toHaveLength(2);
    await wrapper.get(".immersive-decisions button").trigger("click");
    expect(wrapper.emitted("choose")?.[0]).toEqual([choice]);

    await wrapper.get('.immersive-edge-dock[data-edge="right"] button[title="连续创作"]').trigger("click");
    expect(wrapper.emitted("update:open")?.at(-1)).toEqual([["progress", "health", "decisions"]]);
  });

  it("places rules on the right and distributes every project surface", async () => {
    const wrapper = mount(ImmersiveConsole, {
      props: { open: ["quality"], choices: [], prose: [], routeAudits: [] },
      global: { plugins: [createPinia()] },
    });
    expect(wrapper.find('[title="作品管理"]').exists()).toBe(true);
    expect(wrapper.find('[title="创作规则与叙事节奏"]').exists()).toBe(true);
    expect(wrapper.find('[title="作品交付"]').exists()).toBe(true);
    expect(wrapper.find('[title="协议与隐私"]').exists()).toBe(true);
    expect(wrapper.findAll(".immersive-edge-dock")).toHaveLength(4);
    expect(wrapper.get('.immersive-edge-dock[data-edge="left"]').text()).toContain("作品");
    expect(wrapper.get('.immersive-edge-dock[data-edge="right"]').text()).toContain("规则");
    expect(wrapper.get('.immersive-edge-dock[data-edge="bottom"]').text()).toContain("正文长卷");
    expect(wrapper.get('.immersive-edge-dock[data-edge="top"]').text()).toContain("设置");
    expect(wrapper.get(".immersive-console-panel").attributes("data-panel")).toBe("quality");
    expect(wrapper.get(".immersive-console-panel").attributes("data-edge")).toBe("right");
    await wrapper.get('.immersive-edge-dock[data-edge="left"] button[title="作品管理"]').trigger("click");
    expect(wrapper.emitted("update:open")?.at(-1)).toEqual([["projects", "quality"]]);
  });

  it("lets an instrument collapse, move and reset", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    const wrapper = mount(ImmersiveConsole, {
      attachTo: document.body,
      props: { open: ["reader"], choices: [], prose: [], routeAudits: [] },
      global: { plugins: [createPinia()] },
    });
    expect(wrapper.get(".reader-layout").classes()).not.toContain("toc-open");

    const panel = wrapper.get<HTMLElement>(".immersive-console-panel").element;
    vi.spyOn(panel, "getBoundingClientRect").mockReturnValue({ x: 702, y: 62, left: 702, top: 62, right: 1262, bottom: 688, width: 560, height: 626, toJSON: () => ({}) });
    await wrapper.get(".immersive-console-drag").trigger("pointerdown", { button: 0, clientX: 732, clientY: 86 });
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 470, clientY: 250 }));
    window.dispatchEvent(new MouseEvent("pointerup", { clientX: 470, clientY: 250 }));
    await nextTick();
    expect(panel.dataset.dragged).toBe("true");
    expect(panel.style.left).not.toBe("");

    await wrapper.get('[title="复位仪表"]').trigger("click");
    expect(panel.dataset.dragged).toBe("false");
    await wrapper.get('[title="折叠仪表"]').trigger("click");
    expect(panel.classList.contains("collapsed")).toBe(true);
    wrapper.unmount();
    vi.unstubAllGlobals();
  });
});
