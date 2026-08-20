export type QualityMode = "off" | "note" | "blocking";

export interface QualityException {
  rule: string;
  scope: string;
  reason: string;
  mode: QualityMode;
  expires_at: string;
}

export interface QualityProfile {
  name: string;
  preset: string;
  revision: number;
  digest: string;
  thresholds: Record<string, number>;
  rule_modes: Record<string, QualityMode>;
  custom_banned_phrases: string[];
  preferred_habits: string[];
  exceptions: QualityException[];
  [key: string]: unknown;
}
