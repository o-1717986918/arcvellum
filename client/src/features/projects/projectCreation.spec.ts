import { describe, expect, it } from "vitest";
import { isValidTargetLength, TARGET_LENGTH_MIN, TARGET_LENGTH_STEP } from "./projectCreation";

describe("project creation target length", () => {
  it("accepts round ten-thousand targets without shifting the native step base", () => {
    expect(TARGET_LENGTH_MIN).toBe(1_000);
    expect(TARGET_LENGTH_STEP).toBe(1_000);
    expect(isValidTargetLength(30_000)).toBe(true);
    expect(isValidTargetLength(300_000)).toBe(true);
  });
});
