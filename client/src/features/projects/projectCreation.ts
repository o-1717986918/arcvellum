export const TARGET_LENGTH_MIN = 1_000;
export const TARGET_LENGTH_STEP = 1_000;

export function isValidTargetLength(value: number): boolean {
  return Number.isInteger(value)
    && value >= TARGET_LENGTH_MIN
    && (value - TARGET_LENGTH_MIN) % TARGET_LENGTH_STEP === 0;
}
