import type { NarrativeFrame } from "./renderModel";

export function spinePath(frame: NarrativeFrame): number[] {
  const length = Math.max(1200, frame.width);
  const start = frame.centerX - length / 2;
  const points: number[] = [];
  for (let index = 0; index <= 32; index += 1) {
    const progress = index / 32;
    points.push(start + length * progress, frame.centerY + Math.sin(progress * Math.PI * 1.1) * Math.min(180, frame.height * 0.18) - progress * Math.min(160, frame.height * 0.13));
  }
  return points;
}

export function braidPath(side: number, frame: NarrativeFrame): number[] {
  const points: number[] = [];
  const length = Math.max(1500, frame.width);
  for (let index = 0; index <= 36; index += 1) {
    const progress = index / 36;
    points.push(frame.centerX - length / 2 + progress * length, frame.centerY + side * Math.sin(progress * Math.PI * 2.6) * Math.min(210, frame.height * 0.24) - progress * Math.min(150, frame.height * 0.14));
  }
  return points;
}

export function seedFrom(value: string): number {
  let state = 2166136261;
  for (const character of value) state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  return state >>> 0;
}

export function curvePolarity(value: string): number {
  return hashNode(value, 191) % 2 ? 1 : -1;
}

export function pseudo(seed: number): number {
  let value = seed >>> 0;
  value ^= value << 13;
  value ^= value >>> 17;
  value ^= value << 5;
  return (value >>> 0) / 4294967296;
}

export function lerp(start: number, end: number, ratio: number): number {
  return start + (end - start) * ratio;
}

export function mix(first: number, second: number, ratio: number): number {
  const amount = Math.max(0, Math.min(1, ratio));
  const channel = (shift: number) => Math.round((((first >> shift) & 0xff) * (1 - amount)) + (((second >> shift) & 0xff) * amount));
  return (channel(16) << 16) | (channel(8) << 8) | channel(0);
}

function hashNode(value: string, salt: number): number {
  let state = 2166136261 ^ salt;
  for (const character of value) state = Math.imul(state ^ character.charCodeAt(0), 16777619);
  return state >>> 0;
}
