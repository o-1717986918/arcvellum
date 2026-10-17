import { createApp, h } from "vue";
import AgentConversation from "../src/features/project-agent/components/AgentConversation.vue";
import { PROJECT_AGENT_TOOL_LABELS, type ProjectAgentTurnActivity } from "../src/features/project-agent/types";
import "../src/styles/projectAgent.css";

const names = Object.keys(PROJECT_AGENT_TOOL_LABELS);
const activity: ProjectAgentTurnActivity = {
  jobId: "fixture-job", turnId: "fixture-turn", status: "complete", statusLabel: "已完成",
  startedAt: Date.now(), reasoning: "", inputTokens: 0, outputTokens: 0,
  tools: Array.from({ length: 48 }, (_, index) => ({ key: `fixture-${index}`,
    name: index === 47 ? "project_search/" + "long-test-path-".repeat(16) : names[index % names.length],
    label: PROJECT_AGENT_TOOL_LABELS[names[index % names.length]], status: "complete" })),
};
document.head.insertAdjacentHTML("beforeend", `<style>
  *{box-sizing:border-box}body{margin:0}.fixture-shell{display:block;height:100dvh}
  .fixture-note{margin:0;padding:14px 20px;color:var(--pa-muted);font-size:12px;border-bottom:1px solid var(--pa-line)}
  .fixture-shell .pa-conversation{height:calc(100dvh - 48px)}
</style>`);
createApp({ render: () => h("main", { class: "pa-shell pa-theme-dark fixture-shell" }, [
  h("p", { class: "fixture-note" }, "隔离界面验收 · 工具与对话均为测试夹具，未发起模型调用。"),
  h(AgentConversation, { loading: false, omittedCount: 0, hasSession: true, activity,
    messages: [
      { role: "user", payload: { text: "请查看作品进度。" } },
      { role: "assistant", payload: { text: "上一轮回答保留在原来的位置。", turn_id: "previous-turn" } },
      { role: "user", payload: { text: "继续检查已有资料。" } },
      { role: "assistant", payload: { text: "工具调用记录已收在本轮回答上方。展开后可在窗口内滚动查看全部条目，正文保持独立可读。", turn_id: activity.turnId } },
    ],
  }),
]) }).mount("#agent-tool-panel-root");
