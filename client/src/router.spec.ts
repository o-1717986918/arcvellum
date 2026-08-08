import { describe, expect, it } from "vitest";
import { router } from "./router";

describe("public route surface", () => {
  it("opens the production strategy and Agent observatory views", () => {
    const names = new Set(router.getRoutes().map((route) => route.name));

    expect(names.has("strategy")).toBe(true);
    expect(names.has("observatory")).toBe(true);
  });
});
