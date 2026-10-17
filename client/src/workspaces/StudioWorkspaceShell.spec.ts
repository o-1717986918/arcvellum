import { afterEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { createMemoryHistory, createRouter, RouterView } from "vue-router";
import { defineComponent, h } from "vue";
import StudioWorkspaceShell from "./StudioWorkspaceShell.vue";

const counts = vi.hoisted(() => ({ agent: 0, stage: 0, disposed: 0 }));
vi.mock("@/stores/app", async () => {
  const { reactive } = await import("vue");
  const state = reactive({ currentProjectPath: "/works/one" });
  return { useAppStore: () => state };
});
vi.mock("@/features/project-agent/AgentWorkspaceView.vue", async () => {
  const { defineComponent, h, onMounted, onBeforeUnmount } = await import("vue");
  return { default: defineComponent({
    setup() {
      onMounted(() => { counts.agent += 1; });
      onBeforeUnmount(() => { counts.disposed += 1; });
      return () => h("main", { class: "pa-shell" }, [
        h("button", { class: "pa-orrery-entry" }, "进入星仪"),
        h("textarea", { "aria-label": "草稿" }),
        h("div", { class: "conversation" }, "原有会话"),
      ]);
    },
  }) };
});
vi.mock("@/features/workflow/OverviewView.vue", async () => {
  const { defineComponent, h, onMounted, onBeforeUnmount } = await import("vue");
  return { default: defineComponent({
    props: { active: Boolean },
    setup(props) {
      onMounted(() => { counts.stage += 1; });
      onBeforeUnmount(() => { counts.disposed += 1; });
      return () => h("section", { "data-stage-active": String(props.active) }, [
        h("canvas"),
        h("button", { class: "orrery-return-agent" }, "返回工作台"),
      ]);
    },
  }) };
});

let wrapper: VueWrapper | undefined;
async function createStudio(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/agent", name: "project-agent", component: StudioWorkspaceShell },
      { path: "/overview", name: "overview", component: StudioWorkspaceShell },
    ],
  });
  await router.push(path);
  await router.isReady();
  wrapper = mount(defineComponent({ setup: () => () => h(RouterView) }), {
    attachTo: document.body,
    global: { plugins: [router] },
  });
  await flushPromises();
  return router;
}
afterEach(() => {
  wrapper?.unmount();
  wrapper = undefined;
  counts.agent = counts.stage = counts.disposed = 0;
});

describe("persistent studio composition", () => {
  it("folds the interface without replacing the canvas, conversation, draft or scroll position", async () => {
    const router = await createStudio("/agent?session=one");
    const canvas = wrapper!.get("canvas").element;
    const draft = wrapper!.get("textarea");
    await draft.setValue("尚未发送的创作方向");
    const scroller = wrapper!.get(".conversation").element;
    scroller.scrollTop = 184;

    await router.push("/overview?session=one");
    await flushPromises();
    expect(wrapper!.get(".studio-shell").classes()).toContain("studio-immersive");
    expect(wrapper!.get(".studio-interface-layer").attributes("inert")).toBeDefined();
    expect(wrapper!.get("[data-stage-active]").attributes("data-stage-active")).toBe("true");
    expect(wrapper!.get("canvas").element).toBe(canvas);
    expect(counts).toEqual({ agent: 1, stage: 1, disposed: 0 });

    await router.push("/agent?session=one");
    await flushPromises();
    expect(wrapper!.get("textarea").element).toBe(draft.element);
    expect((draft.element as HTMLTextAreaElement).value).toBe("尚未发送的创作方向");
    expect(scroller.scrollTop).toBe(184);
    expect(wrapper!.get(".studio-narrative-layer").attributes("inert")).toBeDefined();
    expect(document.activeElement).toBe(wrapper!.get(".pa-orrery-entry").element);
  });

  it("does not initialize an unseen conversation when opening an Orrery deep link", async () => {
    const router = await createStudio("/overview?session=one");
    expect(counts.agent).toBe(0);
    expect(counts.stage).toBe(1);
    const canvas = wrapper!.get("canvas").element;
    await router.push("/agent?session=one");
    await flushPromises();
    expect(counts.agent).toBe(1);
    expect(wrapper!.get("canvas").element).toBe(canvas);
  });

  it("returns to the original tool on Escape while preserving its session", async () => {
    const router = await createStudio("/overview?session=one&workspaceReturn=reader");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", cancelable: true }));
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("project-agent");
    expect(router.currentRoute.value.query).toEqual({ session: "one", workspace: "reader" });
  });

  it("leaves Escape to an open dialog instead of abandoning the narrative workspace", async () => {
    const router = await createStudio("/overview?session=one");
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    dialog.getClientRects = () => ([{ width: 100, height: 100 }] as unknown as DOMRectList);
    wrapper!.get(".studio-shell").element.append(dialog);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", cancelable: true }));
    await flushPromises();
    expect(router.currentRoute.value.name).toBe("overview");
  });
});
