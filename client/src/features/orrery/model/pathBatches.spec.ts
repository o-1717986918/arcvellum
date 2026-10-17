import { describe, expect, it } from "vitest";
import { batchPaths } from "./pathBatches";

describe("decorative edge batching", () => {
  it("keeps every subpath and separates focused, live and evidence styles", () => {
    const edges = Array.from({ length: 1000 }, (_, i) => ({ id: String(i), path: `M ${i} 0 L ${i} 10`, active: i === 2, live: i === 7, family: i % 2 }));
    const batches = batchPaths(edges, (edge) => [edge.active, edge.live, edge.family]);
    expect(batches.length).toBeLessThan(10);
    expect(batches.reduce((sum, batch) => sum + batch.count, 0)).toBe(edges.length);
    expect(batches.flatMap((batch) => batch.path.match(/M /g) || [])).toHaveLength(edges.length);
    expect(batches.find((batch) => batch.active)?.count).toBe(1);
    expect(batches.find((batch) => batch.live)?.count).toBe(1);
  });
});
