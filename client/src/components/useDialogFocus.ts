import { nextTick, onBeforeUnmount, onMounted, type Ref } from "vue";

/** Keyboard focus belongs to the open modal and returns to its invoker. */
export function useDialogFocus(panel: Ref<HTMLElement | null>, close: () => void): (event: KeyboardEvent) => void {
  const opener = document.activeElement as HTMLElement | null;
  onMounted(() => { panel.value?.querySelector<HTMLElement>("input, button")?.focus(); });
  onBeforeUnmount(() => {
    void nextTick(() => { if (opener?.isConnected) opener.focus({ preventScroll: true }); });
  });
  return (event: KeyboardEvent) => {
    if (event.key === "Escape" && !event.isComposing) { event.preventDefault(); event.stopPropagation(); close(); return; }
    if (event.key !== "Tab") return;
    const controls = Array.from(panel.value?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]',
    ) || []);
    const first = controls[0], last = controls.at(-1);
    if (!first) { event.preventDefault(); panel.value?.focus(); return; }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
}
