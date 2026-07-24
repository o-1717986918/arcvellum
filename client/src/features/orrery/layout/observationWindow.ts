import type { SpatialNarrativeNode } from "@/types/spatial";

export function observationWeight(node: SpatialNarrativeNode, cursor: number, windowSize: number): number {
  const distance = Math.abs(Number(node.time_band || 0) - cursor);
  const radius = Math.max(0.5, windowSize);
  if (distance <= radius) return 1;
  const falloff = Math.min(1, (distance - radius) / Math.max(2, radius * 2.4));
  return 1 - falloff * 0.66;
}

export function defaultObservation(nodes: SpatialNarrativeNode[]): { cursor: number; window: number } {
  const primary = nodes.filter((node) => node.type === "chapter" || node.type === "scene");
  if (!primary.length) return { cursor: 0, window: 3 };
  const active = primary.find((node) => node.completion_state === "active" || node.status === "current");
  const completed = primary.filter((node) => node.completion_state === "completed");
  const fallback = completed.at(-1) || primary[0];
  const bands = primary.map((node) => Number(node.time_band || 0));
  const span = Math.max(...bands) - Math.min(...bands);
  return {
    cursor: Number((active || fallback).time_band || 0),
    window: Math.max(2, Math.min(12, span * 0.12 || 3)),
  };
}
