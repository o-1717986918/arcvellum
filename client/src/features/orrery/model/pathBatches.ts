/** SVG paths are decorative. Batch equal styles, retaining every subpath and edge count. */
export function batchPaths<T extends { id: string; path: string }>(items: T[], style: (item: T) => unknown[]): Array<T & { count: number }> {
  const groups = new Map<string, { first: T; paths: string[] }>();
  for (const item of items) {
    const key = JSON.stringify(style(item));
    const group = groups.get(key);
    if (group) group.paths.push(item.path);
    else groups.set(key, { first: item, paths: [item.path] });
  }
  return [...groups].map(([id, { first, paths }]) => ({ ...first, id, path: paths.join(" "), count: paths.length }));
}
