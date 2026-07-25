import { computed, ref, shallowRef } from "vue";
import type {
  ArchiveAssetDetail,
  ArchiveCandidate,
  ArchiveStructuredDocument,
} from "../types";
import type { ArchiveHistory } from "../types";
import type { AssetDraftSession } from "./archiveSessions";

export function useArchiveEditorState() {
  const selectedAsset = shallowRef<ArchiveAssetDetail | null>(null);
  const selectedCandidate = shallowRef<ArchiveCandidate | null>(null);
  const history = shallowRef<ArchiveHistory>({});
  const draft = ref("");
  const structuredDocument = shallowRef<ArchiveStructuredDocument | null>(null);
  const validation = shallowRef<Record<string, unknown> | null>(null);
  const impact = shallowRef<Record<string, unknown> | null>(null);
  const dirty = computed(() =>
    Boolean(selectedAsset.value && draft.value !== selectedAsset.value.content),
  );

  function snapshot(): AssetDraftSession | null {
    const asset = selectedAsset.value;
    if (!asset) return null;
    return {
      asset,
      draft: draft.value,
      validation: validation.value,
      impact: impact.value,
      structure: structuredDocument.value,
      history: history.value,
    };
  }

  function restore(session: AssetDraftSession): void {
    selectedCandidate.value = null;
    selectedAsset.value = session.asset;
    draft.value = session.draft;
    validation.value = session.validation;
    impact.value = session.impact;
    structuredDocument.value = session.structure;
    history.value = session.history;
  }

  function reset(): void {
    selectedAsset.value = null;
    selectedCandidate.value = null;
    draft.value = "";
    structuredDocument.value = null;
    validation.value = null;
    impact.value = null;
    history.value = {};
  }

  return {
    selectedAsset,
    selectedCandidate,
    history,
    draft,
    structuredDocument,
    validation,
    impact,
    dirty,
    snapshot,
    restore,
    reset,
  };
}
