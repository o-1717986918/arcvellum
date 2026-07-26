import { ref } from "vue";
import { defineStore } from "pinia";

export const useReaderNavigationStore = defineStore("readerNavigation", () => {
  const requestedUnitId = ref("");
  const activeUnitId = ref("");
  const requestSequence = ref(0);

  function request(unitId: string): void {
    const value = unitId.trim();
    if (!value) return;
    requestedUnitId.value = value;
    requestSequence.value += 1;
  }

  function activate(unitId: string): void {
    activeUnitId.value = unitId.trim();
  }

  function reset(): void {
    requestedUnitId.value = "";
    activeUnitId.value = "";
    requestSequence.value = 0;
  }

  return { requestedUnitId, activeUnitId, requestSequence, request, activate, reset };
});
