import { describe, expect, it } from "vitest";
import { applySoftMigrationChanges } from "./useQualityProfile";
import type { QualityProfile } from "./types";

describe("quality profile migration", () => {
  it("changes only eligible soft rules without replacing unsaved edits", () => {
    const profile = {
      name: "自定义", preset: "balanced", revision: 3, digest: "old",
      thresholds: { commas_per_sentence: 6 },
      rule_modes: { "staccato-period-overuse": "blocking", "ascii-punctuation": "blocking" },
      custom_banned_phrases: ["自定义禁词"], preferred_habits: [], exceptions: [],
    } satisfies QualityProfile;
    const result = applySoftMigrationChanges(profile, [
      { rule: "staccato-period-overuse", from: "blocking", to: "note" },
      { rule: "ascii-punctuation", from: "blocking", to: "off" },
    ]);
    expect(result).toBe(profile);
    expect(result.rule_modes["staccato-period-overuse"]).toBe("note");
    expect(result.rule_modes["ascii-punctuation"]).toBe("blocking");
    expect(result.custom_banned_phrases).toEqual(["自定义禁词"]);
    expect(result.thresholds.commas_per_sentence).toBe(6);
  });
});
