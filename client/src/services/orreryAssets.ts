import type { OrreryBackground } from "@/services/orreryPreferences";

type BackgroundLoader = () => Promise<string>;

const loaders: Partial<Record<OrreryBackground, BackgroundLoader>> = {
  mineral: () => import("@/assets/orrery/mineral-astrarium.webp").then((module) => module.default),
};

const loaded = new Map<OrreryBackground, string>();

export async function loadOrreryBackground(background: OrreryBackground): Promise<string> {
  const cached = loaded.get(background);
  if (cached !== undefined) return cached;
  const loader = loaders[background];
  if (!loader) return "";
  const source = await loader();
  loaded.set(background, source);
  return source;
}
