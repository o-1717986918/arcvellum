import { ref } from "vue";
import { defineStore } from "pinia";
import type { NarrativeFocusLevel } from "@/features/orrery/model/focusScope";
import type { OrreryHeatLens } from "@/features/orrery/model/exploration";
import type { SpatialGrammar } from "@/types/spatial";

const STORAGE_KEY = "arcvellum.orreryBookmarks.v1";

export interface OrreryViewBookmark {
  id: string;
  projectRoot: string;
  label: string;
  level: NarrativeFocusLevel;
  focus: string;
  grammar: SpatialGrammar;
  timeCursor: number;
  timeWindow: number;
  heatLens: OrreryHeatLens;
  nodeId: string;
  createdAt: string;
}

export const useOrreryExplorationStore = defineStore("orreryExploration", () => {
  const bookmarks = ref<OrreryViewBookmark[]>(readBookmarks());

  function forProject(projectRoot: string): OrreryViewBookmark[] {
    return bookmarks.value.filter((item) => item.projectRoot === projectRoot);
  }

  function save(input: Omit<OrreryViewBookmark, "id" | "createdAt">): OrreryViewBookmark {
    const item: OrreryViewBookmark = {
      ...input,
      id: `view-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
      createdAt: new Date().toISOString(),
    };
    const other = bookmarks.value.filter((entry) => entry.projectRoot !== input.projectRoot);
    const project = [item, ...forProject(input.projectRoot)].slice(0, 12);
    bookmarks.value = [...other, ...project];
    persist(bookmarks.value);
    return item;
  }

  function remove(id: string): void {
    bookmarks.value = bookmarks.value.filter((item) => item.id !== id);
    persist(bookmarks.value);
  }

  return { bookmarks, forProject, save, remove };
});

function readBookmarks(): OrreryViewBookmark[] {
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(value) ? value.filter(validBookmark) : [];
  } catch {
    return [];
  }
}

function persist(items: OrreryViewBookmark[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // A private browsing quota should not block the workbench.
  }
}

function validBookmark(value: unknown): value is OrreryViewBookmark {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<OrreryViewBookmark>;
  return Boolean(item.id && item.projectRoot && item.level && item.grammar);
}
