import { describe, expect, it } from "vitest";
import { deliveryReadiness } from "./deliveryReadiness";

describe("delivery readiness presentation", () => {
  it("blocks an empty project before invoking the formal workflow", () => {
    expect(deliveryReadiness(0, 0, 0)).toMatchObject({ allowed: false, label: "等待正式正文" });
  });

  it("surfaces projected blockers before enabling delivery", () => {
    expect(deliveryReadiness(12_000, 4, 2, 3)).toMatchObject({ allowed: false, label: "先完成交付前检查" });
  });

  it("keeps a partial manuscript out of formal delivery until integrity closes", () => {
    expect(deliveryReadiness(5_281, 3, 0, 3)).toMatchObject({ allowed: false, label: "等待作品完成" });
  });

  it("allows delivery when formal reading content exists and every integrity check passes", () => {
    expect(deliveryReadiness(12_000, 4, 0, 0).allowed).toBe(true);
  });
});
