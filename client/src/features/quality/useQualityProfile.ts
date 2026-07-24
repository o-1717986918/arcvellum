import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api } from "@/services/api";
import { useAppStore } from "@/stores/app";

export type QualityMode = "off" | "note" | "blocking";
export interface QualityException { rule: string; scope: string; reason: string; mode: QualityMode; expires_at: string }
export interface QualityProfile {
  name: string;
  preset: string;
  revision: number;
  digest: string;
  thresholds: Record<string, number>;
  rule_modes: Record<string, QualityMode>;
  custom_banned_phrases: string[];
  preferred_habits: string[];
  exceptions: QualityException[];
  [key: string]: unknown;
}

export const QUALITY_RULES = [
  ["mechanical-contrast-frame", "生硬对照", "拦住“不是……而是……”及其标点变体。"],
  ["contrast-evasion-frame", "换皮转折", "识别“看似……其实……”等同功能替换。"],
  ["plain-narration-banned-expression", "套话与器官反应", "提示嘴角、眼底、呼吸等高频代写。"],
  ["dash-overuse", "破折号密度", "按每 100 个叙事单元和单段双重判断。"],
  ["staccato-period-overuse", "碎句密度", "避免把同一语义链切成均匀短句。"],
  ["mechanical-transition-overuse", "显性转折词", "控制但是、然而、于是、突然的机械接榫。"],
  ["simile-dependency", "比喻依赖", "避免用好像、仿佛和万能比喻撑情绪。"],
  ["slogan-like-ending", "金句式收尾", "提醒主题直说和整齐反转句。"],
] as const;

export function useQualityProfile() {
  const store = useAppStore();
  const profile = ref<QualityProfile | null>(null);
  const previewText = ref("灶上的鱼羹热了第三遍，她还没等到那个人回来。门外不是风声，而是有人停在台阶下。她嘴角微扬，仿佛命运的齿轮终于开始转动。");
  const preview = ref<Record<string, any> | null>(null);
  const previewScope = ref("");
  const loading = ref(false);
  const saving = ref(false);
  const dirty = ref(false);
  const message = ref("");
  const error = ref("");
  let previewTimer = 0;
  let previewRevision = 0;
  let loadedProject = "";

  const statusLabel = computed(() => preview.value?.status === "blocking"
    ? "需要修改"
    : preview.value?.status === "notes"
      ? "有表达提醒"
      : "通过当前规则");
  const findings = computed(() => [...(preview.value?.blocking || []), ...(preview.value?.notes || [])]);

  async function load(): Promise<void> {
    if (!store.currentProjectPath) return;
    const projectPath = store.currentProjectPath;
    if (loadedProject && loadedProject !== projectPath) profile.value = null;
    loading.value = true;
    error.value = "";
    try {
      const result = await api<{ profile: QualityProfile }>(`/project/creative-quality?project_root=${encodeURIComponent(projectPath)}`);
      if (store.currentProjectPath !== projectPath) return;
      profile.value = result.profile;
      loadedProject = projectPath;
      dirty.value = false;
      await runPreview();
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "暂时无法读取创作规则。";
    } finally {
      loading.value = false;
    }
  }

  async function runPreview(): Promise<void> {
    if (!profile.value || !store.currentProjectPath) return;
    const revision = ++previewRevision;
    try {
      const result = await api<Record<string, unknown>>("/project/creative-quality/preview", {
        method: "POST",
        body: JSON.stringify({
          project_root: store.currentProjectPath,
          text: previewText.value,
          profile: profile.value,
          scope: previewScope.value,
        }),
      });
      if (revision === previewRevision) preview.value = result;
    } catch (cause) {
      if (revision === previewRevision) {
        error.value = cause instanceof Error ? cause.message : "即时样文检查暂时不可用。";
      }
    }
  }

  function schedulePreview(): void {
    dirty.value = true;
    message.value = "";
    window.clearTimeout(previewTimer);
    previewTimer = window.setTimeout(() => void runPreview(), 180);
  }

  async function save(): Promise<void> {
    if (!profile.value || !store.currentProjectPath) return;
    saving.value = true;
    message.value = "";
    error.value = "";
    try {
      const result = await api<{ profile: QualityProfile }>("/project/creative-quality", {
        method: "PUT",
        body: JSON.stringify({ project_root: store.currentProjectPath, profile: profile.value }),
      });
      profile.value = result.profile;
      dirty.value = false;
      message.value = "规则已保存。它会从下一份候选正文开始生效，旧稿需要重新审查。";
      await runPreview();
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "规则保存失败，未保存的调整仍保留在窗口中。";
    } finally {
      saving.value = false;
    }
  }

  function applyPreset(preset: string): void {
    if (!profile.value) return;
    profile.value.preset = preset;
    const values: Record<string, number[]> = {
      balanced: [2, 2, 4, 2],
      plainspoken: [1, .5, 2, 1],
      "style-led": [3, 4, 5, 4],
    };
    const [soft, dash, transitions, simile] = values[preset] || values.balanced;
    Object.assign(profile.value.thresholds, {
      soft_density_per_100_units: soft,
      dash_per_100_units: dash,
      transition_per_100_units: transitions,
      simile_per_100_units: simile,
    });
    schedulePreview();
  }

  function addException(): void {
    if (!profile.value) return;
    profile.value.exceptions ||= [];
    profile.value.exceptions.push({
      rule: "mechanical-contrast-frame",
      scope: "scene_0001",
      reason: "本场景的已登记文风需要",
      mode: "note",
      expires_at: "",
    });
    schedulePreview();
  }

  function removeException(index: number): void {
    profile.value?.exceptions.splice(index, 1);
    schedulePreview();
  }

  onBeforeUnmount(() => window.clearTimeout(previewTimer));
  watch(
    () => store.currentProjectPath,
    (next, previous) => {
      if (next && next !== previous) void load();
    },
  );

  return {
    profile,
    previewText,
    preview,
    previewScope,
    loading,
    saving,
    dirty,
    message,
    error,
    statusLabel,
    findings,
    rules: QUALITY_RULES,
    load,
    runPreview,
    schedulePreview,
    save,
    applyPreset,
    addException,
    removeException,
  };
}
