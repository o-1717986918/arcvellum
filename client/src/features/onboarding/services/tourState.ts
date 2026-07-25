const STORAGE_PREFIX = "arcvellum.module-tour";

export function hasCompletedTour(tourId: string, version: number): boolean {
  return window.localStorage.getItem(storageKey(tourId, version)) === "1";
}

export function markTourCompleted(tourId: string, version: number): void {
  window.localStorage.setItem(storageKey(tourId, version), "1");
}

export function resetTour(tourId: string, version: number): void {
  window.localStorage.removeItem(storageKey(tourId, version));
}

function storageKey(tourId: string, version: number): string {
  return `${STORAGE_PREFIX}.${tourId}.v${version}`;
}
