export type CreativeRuntime = "pi-worker";

const KEY = "arcvellum.creativeRuntime";

export function readCreativeRuntime(): CreativeRuntime {
  return "pi-worker";
}

export function saveCreativeRuntime(value: CreativeRuntime): CreativeRuntime {
  localStorage.setItem(KEY, value);
  return value;
}
