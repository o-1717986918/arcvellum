"""Deterministic demo project builder for the full agentic workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .context_packet import build_context_packet
from .init_project import InitOptions, init_work_project
from .platform_agent_tasks import (
    write_platform_asset_creation_task,
    write_platform_canon_review_task,
    write_platform_committee_task,
    write_platform_scene_review_task,
)
from .review_ci import review_scene_draft
from .scene_draft import build_scene_draft
from .workflow_runner import run_workflow


@dataclass(frozen=True)
class DemoProjectResult:
    root: Path
    draft_path: Path
    review_path: Path
    agent_scene_review: Path
    agent_canon_review: Path
    committee_review: Path
    workflow_state: Path | None
    report_path: Path
    asset_candidates: tuple[Path, ...] = ()


def build_demo_project(target: Path, *, title: str = "文学工程 Demo", run_agent_workflow: bool = True) -> DemoProjectResult:
    root = target.resolve()
    init_work_project(
        InitOptions(
            target=root,
            title=title,
            premise="一次城市停电迫使调查者面对被压下的旧档案。",
            genre="悬疑 / 文学工程演示",
            target_length=12000,
        )
    )
    asset_tasks = [
        write_platform_asset_creation_task(root, asset_type="world", brief="为 demo 项目生成世界观候选。"),
        write_platform_asset_creation_task(root, asset_type="character", brief="为 demo 项目生成角色候选。"),
        write_platform_asset_creation_task(root, asset_type="outline", brief="为 demo 项目生成大纲候选。"),
    ]
    _write_character(root)
    _write_scene(root)
    build_context_packet(root, scene=Path("scenes/scene_0001.yaml"), rebuild_index=True)
    draft = build_scene_draft(root, scene=Path("scenes/scene_0001.yaml")).draft_path
    _fill_draft(draft)
    review = review_scene_draft(root, draft)
    agent_scene = write_platform_scene_review_task(root, scene_path=root / "scenes" / "scene_0001.yaml", draft_path=draft)
    agent_canon = write_platform_canon_review_task(root)
    committee = write_platform_committee_task(root, subject="demo-scene-0001", source=draft)
    workflow_state = None
    if run_agent_workflow:
        workflow = run_workflow(
            root,
            mode="scene-loop",
            scene=Path("scenes/scene_0001.yaml"),
            run_id="demo-agent-scene-loop",
            agent_review=True,
            overwrite_run=True,
        )
        workflow_state = workflow.state_path
    report_path = root / "reviews" / "agent" / "demo_walkthrough.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _render_report(
            root,
            draft,
            review.report_path,
            agent_scene.task_path,
            agent_canon.task_path,
            committee.task_path,
            workflow_state,
            tuple(item.task_path for item in asset_tasks),
        ),
        encoding="utf-8",
    )
    return DemoProjectResult(
        root=root,
        draft_path=draft,
        review_path=review.report_path,
        agent_scene_review=agent_scene.task_path,
        agent_canon_review=agent_canon.task_path,
        committee_review=committee.task_path,
        workflow_state=workflow_state,
        report_path=report_path,
        asset_candidates=tuple(item.task_path for item in asset_tasks),
    )


def _write_character(root: Path) -> None:
    (root / "characters" / "linzhou.yaml").write_text(
        """character_id: linzhou
name: 林舟
role: 主角
identity: 城市档案调查者
background_story:
  summary: 少年时一次仓促判断让同伴背负误解，因此他习惯在行动前反复确认旁人的处境。
  formative_events:
    - 少年时期的误判让他对“看似显然”的证据保持警惕。
  behavior_influences:
    - 做决定前先观察现场细节。
    - 面对旧档案时会压低情绪反应。
    - 如果行动可能牵连同伴，会选择更慢但更稳妥的路径。
  reveal_policy: implicit_only
bdi:
  belief:
    - 城市停电与旧档案被隐藏有关。
  desire:
    - 找到档案失踪的真实原因。
  intention:
    - 在不惊动看守的情况下进入旧楼。
psychology:
  fear:
    - 再次因自己的判断牵连别人。
  secret:
    - 他曾读过一页被撕下的档案。
  moral_line: 不伤害无辜者。
relationships:
  - character: 未命名同伴
    state: 信任但有所隐瞒
speech_style:
  rhythm: 短句，克制，少解释。
arc:
  current: 从旁观转向主动调查。
state:
  location: 旧楼外
  emotional: 克制紧张
  knowledge:
    - 知道残缺档案可能与停电相关。
""",
        encoding="utf-8",
    )


def _write_scene(root: Path) -> None:
    (root / "scenes" / "scene_0001.yaml").write_text(
        """scene_id: scene_0001
chapter_id: chapter_0001
status: planned
time:
  story_time: 停电当晚
  timeline_order: 1
location: 旧楼门口
participants:
  - linzhou
input_state:
  canon_refs: []
  character_states:
    - linzhou: 克制紧张，正在接近旧楼。
  active_foreshadowing:
    - 残缺档案
scene_goal: 林舟确认旧楼停电与残缺档案有关，并决定进入旧楼。
conflict:
  external: 巡逻灯随时可能转向旧楼门口。
  internal: 林舟害怕仓促行动再次牵连同伴。
actions:
  - 林舟观察巡逻灯。
  - 林舟压低手电进入旧楼。
revealed_info:
  - 旧楼停电并非偶然。
emotional_curve:
  - 克制
  - 警觉
  - 决断
style_constraints:
  - 克制叙述
output_state:
  new_facts: []
  character_changes: []
  relationship_changes: []
  foreshadowing_changes: []
  next_hooks:
    - 门后的灰尘像刚被人推开。
review:
  canon_test: pending
  character_test: pending
  plot_test: pending
  style_test: pending
""",
        encoding="utf-8",
    )


def _fill_draft(draft: Path) -> None:
    text = draft.read_text(encoding="utf-8")
    body = (
        "林舟站在旧楼门口，先看巡逻灯，再看门缝下那道不合时宜的灰。停电让整条街暗下来，"
        "可旧楼里面有一截电流声，低得像有人把话咽回去。他没有立刻进去，只把手电压低，"
        "数了三次呼吸。少年时那次误判并没有在这里被说出口，却让他的手指停在门把上，"
        "直到确认街角无人经过，才慢慢推开门。灰尘向里卷，像刚有人从黑暗里退走。"
    )
    replacements = {
        "<!-- 在这里写入场景正文。 -->": body,
        "### 新增事实候选\n\n- ": "### 新增事实候选\n\n- 林舟发现旧楼停电与残缺档案存在关联。",
        "### 人物状态变化\n\n- ": "### 人物状态变化\n\n- 林舟从观察转入主动调查。",
        "### 关系变化\n\n- ": "### 关系变化\n\n- 林舟继续向同伴隐瞒进入旧楼的行动。",
        "### 伏笔变化\n\n- ": "### 伏笔变化\n\n- 门后灰尘异常成为后续追查线索。",
        "### 需要人工确认\n\n- ": "### 需要人工确认\n\n- 是否确认旧楼停电为主线事件。",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    draft.write_text(text, encoding="utf-8")


def _render_report(root: Path, draft: Path, review: Path, agent_scene: Path, agent_canon: Path, committee: Path, workflow_state: Path | None, asset_candidates: tuple[Path, ...]) -> str:
    lines = [
        "# Demo Walkthrough",
        "",
        "这个 demo 使用自造文本，不依赖受版权限制语料。",
        "",
        f"- Draft: `{_rel(draft, root)}`",
        f"- Rule Review: `{_rel(review, root)}`",
        f"- Platform Agent Scene Review Task: `{_rel(agent_scene, root)}`",
        f"- Platform Agent Canon Review Task: `{_rel(agent_canon, root)}`",
        f"- Platform Agent Committee Task: `{_rel(committee, root)}`",
    ]
    for candidate in asset_candidates:
        lines.append(f"- Platform Agent Asset Task: `{_rel(candidate, root)}`")
    if workflow_state:
        lines.append(f"- Workflow State: `{_rel(workflow_state, root)}`")
    return "\n".join(lines) + "\n"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)
