import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { useReaderNavigationStore } from "@/stores/readerNavigation";

describe("reader navigation store", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("keeps an explicit request sequence even when the same unit is requested again", () => {
    const store = useReaderNavigationStore();
    store.request("unit-1");
    store.request("unit-1");
    expect(store.requestedUnitId).toBe("unit-1");
    expect(store.requestSequence).toBe(2);
  });

  it("tracks the unit currently visible in the manuscript reader", () => {
    const store = useReaderNavigationStore();
    store.activate("unit-2");
    expect(store.activeUnitId).toBe("unit-2");
    store.reset();
    expect(store.activeUnitId).toBe("");
  });
});
