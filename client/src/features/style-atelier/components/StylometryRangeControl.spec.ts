import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import StylometryRangeControl from "./StylometryRangeControl.vue";
import type { MetricRow } from "../stylometryTypes";
const metric: MetricRow = { id: "sentence_length_han", label: "句群节奏", unit: "汉字/句", group: "primary",
  observed: 12.3456, floor: 1, ceiling: null, available: true, suggested: { min: 10, max: 20 }, source_range: { p25: 10, p75: 20 } };
const target = { id: metric.id, unit: metric.unit, min: 9.125, max: 24.875, enabled: true };
describe("measured style interval", () => {
  it("keeps imported precision, clamps crossed handles, and accepts larger numeric ranges", async () => {
    const wrapper = mount(StylometryRangeControl, { props: { metric, target, disabled: false } });
    expect(wrapper.get('input[aria-label="句群节奏目标下界"]').element).toHaveProperty("value", "9.125");
    await wrapper.get('input[aria-label="句群节奏下界滑块"]').setValue("30");
    expect(wrapper.emitted("update")?.[0][0]).toMatchObject({ min: 24.875, max: 24.875 });
    await wrapper.get('input[aria-label="句群节奏目标上界"]').setValue("800.125");
    const large = wrapper.emitted("update")?.[1][0] as typeof target;
    expect(large.max).toBe(800.125); await wrapper.setProps({ target: large });
    expect(Number(wrapper.get('input[aria-label="句群节奏上界滑块"]').attributes("max"))).toBeGreaterThanOrEqual(800.125);
  });
  it("uses the measurement's real ratio domain and disables missing source evidence", async () => {
    const ratio = { ...metric, id: "leaf_share", ceiling: 1, floor: 0, available: false };
    const wrapper = mount(StylometryRangeControl, { props: { metric: ratio, target: { ...target, min: .2, max: .4 }, disabled: false } });
    expect(wrapper.get('input[type="range"]').attributes("max")).toBe("1");
    expect(wrapper.get('input[type="range"]').attributes("disabled")).toBeDefined();
    expect(wrapper.get('input[type="checkbox"]').attributes("disabled")).toBeDefined();
  });
});
