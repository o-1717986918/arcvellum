import type { OrreryBackground } from "@/services/orreryPreferences";

type BackgroundLoader = () => Promise<string>;

const loaders: Partial<Record<OrreryBackground, BackgroundLoader>> = {
  mineral: () => import("@/assets/orrery/mineral-astrarium.webp").then((module) => module.default),
  archive: () => import("@/assets/orrery/night-archive.webp").then((module) => module.default),
  ink: () => import("@/assets/orrery/living-ink-cosmos.webp").then((module) => module.default),
  iris: () => import("@/assets/orrery/iris-celestial-cartography.webp").then((module) => module.default),
  obsidian: () => import("@/assets/orrery/obsidian-brass-astrarium.webp").then((module) => module.default),
  bookcase: () => import("@/assets/orrery/bookcase-literary-observatory.webp").then((module) => module.default),
  modern: () => import("@/assets/orrery/modern-graphite-observatory.webp").then((module) => module.default),
};

const loaded = new Map<OrreryBackground, string>();

export async function loadOrreryBackground(background: OrreryBackground): Promise<string> {
  if (background === "plain") return "";
  const cached = loaded.get(background);
  if (cached !== undefined) return cached;
  const loader = loaders[background];
  if (!loader) return "";
  const source = await loader();
  loaded.set(background, source);
  return source;
}
