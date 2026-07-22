export type OrreryEngine = "spatial";

const ENGINE_STORAGE_KEY = "arcvellum.orreryEngine";

export function normalizeOrreryEngine(value: unknown): OrreryEngine {
  void value;
  return "spatial";
}

export function preferredOrreryEngine(): OrreryEngine {
  // Migrate older preferences and legacy deep links to the spatial stage. The
  // accessible list inside that stage is the only user-facing fallback.
  localStorage.setItem(ENGINE_STORAGE_KEY, "spatial");
  return "spatial";
}

export function savePreferredOrreryEngine(value: OrreryEngine): void {
  void value;
  localStorage.setItem(ENGINE_STORAGE_KEY, "spatial");
}
