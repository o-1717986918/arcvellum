import { ref } from "vue";
import { defineStore } from "pinia";
import { api, query } from "@/services/api";
import type { HumanChoiceReceipt } from "@/types/api";

type Choice = Record<string, unknown>;

export const useHumanChoicesStore = defineStore("human-choices", () => {
  const choices = ref<Choice[]>([]);
  const selectedChoice = ref<Choice | null>(null);
  const rationale = ref("");
  const busy = ref(false);
  const completed = ref(false);
  const message = ref("");
  const error = ref("");
  const loadedProject = ref("");
  let requestSequence = 0;

  async function load(projectRoot: string): Promise<void> {
    const root = projectRoot.trim();
    const sequence = ++requestSequence;
    if (!root) {
      reset();
      return;
    }
    const result = await api<{ items?: Choice[]; choices?: Choice[] }>(
      `/workflow/current-choice?${query({ project_root: root })}`,
    );
    if (sequence !== requestSequence) return;
    loadedProject.value = root;
    choices.value = result.items || result.choices || [];
    if (
      selectedChoice.value
      && !choices.value.some((choice) => choice.choice_id === selectedChoice.value?.choice_id)
      && !completed.value
    ) {
      close();
    }
  }

  function open(choice: Choice): void {
    selectedChoice.value = choice;
    rationale.value = "";
    message.value = "";
    error.value = "";
    completed.value = false;
  }

  function close(): void {
    selectedChoice.value = null;
    rationale.value = "";
    message.value = "";
    error.value = "";
    completed.value = false;
  }

  async function submit(projectRoot: string, option: Choice): Promise<HumanChoiceReceipt> {
    if (!selectedChoice.value || busy.value) throw new Error("当前没有可提交的创作选择。");
    const selected = String(option.id || option.label || "").trim();
    if (!selected) throw new Error("这个选项缺少可提交的标识，请刷新项目后重试。");
    const choice = selectedChoice.value;
    busy.value = true;
    error.value = "";
    try {
      const receipt = await api<HumanChoiceReceipt>("/workflow/human-choice", {
        method: "POST",
        body: JSON.stringify({
          project_root: projectRoot,
          choice_id: choice.choice_id,
          route: choice.route,
          task_id: choice.task_id || "",
          decision_type: choice.decision_type,
          target: choice.target || {},
          options: choice.options || [],
          selected,
          rationale: rationale.value || `用户在 ArcVellum 中确认“${String(option.label || option.id)}”。`,
          actor: "arcvellum-user",
        }),
      });
      const effect = (
        receipt.effect && typeof receipt.effect === "object"
          ? receipt.effect
          : {}
      ) as Record<string, unknown>;
      message.value = String(effect.summary || receipt.materialized || "选择已写入正式流程。");
      completed.value = receipt.consumed;
      if (receipt.consumed) {
        choices.value = choices.value.filter((item) => item.choice_id !== receipt.choice_id);
      }
      await load(projectRoot);
      return receipt;
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "暂时无法记录这项选择。";
      throw cause;
    } finally {
      busy.value = false;
    }
  }

  function reset(): void {
    requestSequence += 1;
    choices.value = [];
    loadedProject.value = "";
    close();
  }

  return {
    choices,
    selectedChoice,
    rationale,
    busy,
    completed,
    message,
    error,
    loadedProject,
    load,
    open,
    close,
    submit,
    reset,
  };
});
