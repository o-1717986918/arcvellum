export type CreativeRuntime = "pi-worker" | "opencode";

const KEY = "arcvellum.creativeRuntime";

export function readCreativeRuntime(): CreativeRuntime {
  const value = localStorage.getItem(KEY);
  return value === "opencode" ? "opencode" : "pi-worker";
}

export function saveCreativeRuntime(value: CreativeRuntime): CreativeRuntime {
  localStorage.setItem(KEY, value);
  return value;
}
