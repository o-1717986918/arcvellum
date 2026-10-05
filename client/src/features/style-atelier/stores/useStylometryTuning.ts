import { computed, onBeforeUnmount, ref, watch, type Ref } from "vue";
import { stylometryClient } from "../services/stylometryClient";
import type { FragmentRequest, StyloCompiled } from "../stylometryTypes";

export function useStylometryTuning(input: Ref<FragmentRequest | null>, fragment: Ref<string>,
  compiled: Ref<StyloCompiled | null>, publish: (input: FragmentRequest, body: string, current: () => boolean) => Promise<boolean>) {
  const previewBusy = ref(false), previewError = ref(""), autoMount = ref(false), publishing = ref(false);
  const manualFragment = ref(false), readySignature = ref("");
  let timer: ReturnType<typeof setTimeout> | undefined, sequence = 0, disposed = false;
  const signature = () => JSON.stringify(input.value);
  const previewCurrent = computed(() => readySignature.value === signature());
  function reset(manual = false) {
    sequence++; clearTimeout(timer); readySignature.value = "";
    autoMount.value = false; manualFragment.value = manual; previewError.value = ""; previewBusy.value = false;
    schedule();
  }
  function adopt(result: StyloCompiled, key: string) {
    const manual = manualFragment.value;
    compiled.value = result; readySignature.value = key;
    if (!manual) fragment.value = result.fragment_text;
  }
  function schedule() {
    clearTimeout(timer);
    if (input.value && !disposed) timer = setTimeout(() => void refresh(), 350);
  }
  async function refresh() {
    clearTimeout(timer);
    const request = input.value, key = signature(), ticket = ++sequence;
    if (!request) return;
    previewBusy.value = true; previewError.value = "";
    try {
      const result = await stylometryClient.compile({ ...request });
      if (disposed || ticket !== sequence || key !== signature()) return;
      adopt(result, key);
      if (autoMount.value && !manualFragment.value) await applyAndMount();
    } catch (error) {
      if (!disposed && ticket === sequence && key === signature()) {
        previewError.value = error instanceof Error ? error.message : String(error);
        autoMount.value = false;
      }
    } finally { if (ticket === sequence) previewBusy.value = false; }
  }
  async function applyAndMount() {
    const request = input.value, key = signature();
    const automatic = autoMount.value;
    if (!request || publishing.value || disposed) return;
    publishing.value = true; previewError.value = "";
    try {
      if (!previewCurrent.value || !compiled.value) {
        const result = await stylometryClient.compile({ ...request });
        if (disposed || key !== signature()) return;
        adopt(result, key);
      }
      const saved = await publish({ ...request }, fragment.value,
        () => !disposed && key === signature() && (!automatic || autoMount.value));
      if (!saved && key === signature()) autoMount.value = false;
    } catch (error) {
      if (!disposed && key === signature()) {
        previewError.value = error instanceof Error ? error.message : String(error);
        autoMount.value = false;
      }
    } finally {
      publishing.value = false;
      if (!disposed && autoMount.value && key !== signature()) schedule();
    }
  }
  function takePreview() {
    if (!compiled.value || !previewCurrent.value) return;
    manualFragment.value = false; fragment.value = compiled.value.fragment_text;
  }
  watch(input, () => { sequence++; schedule(); }, { deep: true, flush: "sync" });
  watch(fragment, value => {
    manualFragment.value = Boolean(value.trim() && value !== compiled.value?.fragment_text);
    if (manualFragment.value) autoMount.value = false;
  }, { flush: "sync" });
  watch(autoMount, enabled => { if (enabled) schedule(); });
  onBeforeUnmount(() => { disposed = true; reset(); });
  return { previewBusy, previewError, previewCurrent, autoMount, publishing, manualFragment,
    reset, refresh, takePreview, applyAndMount };
}
