export interface LabelRectangle { left: number; right: number; top: number; bottom: number }

/** Screen-space broad phase; preserves the exact label overlap rule. */
export class LabelOccupancy {
  private cells = new Map<string, LabelRectangle[]>();

  add(rect: LabelRectangle): void {
    for (const key of this.keys(rect)) {
      const bucket = this.cells.get(key) || [];
      bucket.push(rect);
      this.cells.set(key, bucket);
    }
  }

  overlaps(rect: LabelRectangle): boolean {
    for (const key of this.keys(rect)) for (const other of this.cells.get(key) || []) {
      if (!(rect.right + 8 < other.left || other.right + 8 < rect.left
        || rect.bottom + 6 < other.top || other.bottom + 6 < rect.top)) return true;
    }
    return false;
  }

  private *keys(rect: LabelRectangle): Generator<string> {
    for (let x = Math.floor((rect.left - 8) / 96); x <= Math.floor((rect.right + 8) / 96); x++) {
      for (let y = Math.floor((rect.top - 6) / 64); y <= Math.floor((rect.bottom + 6) / 64); y++) yield `${x}:${y}`;
    }
  }
}
