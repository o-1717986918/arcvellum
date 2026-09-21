import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import NarrativeParallaxStage from "./NarrativeParallaxStage.vue";
import { NarrativeParallaxRenderer } from "./engine/parallaxRenderer";
import type { SpatialLayout, SpatialNarrativeProjection } from "@/types/spatial";

vi.mock("./engine/parallaxRenderer", () => ({
  NarrativeParallaxRenderer: { create: vi.fn() },
}));

describe("NarrativeParallaxStage", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("recovers the GPU scene when desktop initialization finishes after the static preview appears", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("ResizeObserver", class {
      observe() {}
      disconnect() {}
    });
    let resolveRenderer!: (value: unknown) => void;
    const pending = new Promise((resolve) => { resolveRenderer = resolve; });
    vi.mocked(NarrativeParallaxRenderer.create).mockReturnValue(pending as ReturnType<typeof NarrativeParallaxRenderer.create>);
    const renderer = {
      onAnchors: vi.fn(), onContextLost: vi.fn(), onContextRestored: vi.fn(),
      resize: vi.fn(), update: vi.fn(), fit: vi.fn(), dispose: vi.fn(),
    };
    const projection = { revision: "scene-1", nodes: [], edges: [] } as unknown as SpatialNarrativeProjection;
    const layout = { revision: "layout-1", points: new Map() } as unknown as SpatialLayout;
    const wrapper = mount(NarrativeParallaxStage, { props: { projection, layout } });
    await nextTick();
    await vi.advanceTimersByTimeAsync(1601);
    expect(wrapper.emitted("degraded")).toHaveLength(1);

    resolveRenderer(renderer);
    await flushPromises();
    expect(wrapper.emitted("recovered")).toHaveLength(1);
    expect(renderer.fit).toHaveBeenCalledOnce();
    const onLost = renderer.onContextLost.mock.calls[0]?.[0] as (() => void) | undefined;
    const onRestored = renderer.onContextRestored.mock.calls[0]?.[0] as (() => void) | undefined;
    onLost?.();
    expect(wrapper.emitted("degraded")).toHaveLength(2);
    expect(renderer.dispose).not.toHaveBeenCalled();
    onRestored?.();
    expect(wrapper.emitted("recovered")).toHaveLength(2);
    expect(renderer.fit).toHaveBeenCalledTimes(2);
    wrapper.unmount();
    expect(renderer.dispose).toHaveBeenCalledOnce();
  });
});
