"""Ordered navigation for prompts that can reach a current creative Agent."""

from __future__ import annotations

from typing import Any


_FLOW = (
    ("direction", "01 · 作品方向", (
        ("direction.project", "作品总编与场间交接"),
        ("direction.advice", "顾问与自动判断"),
    )),
    ("source", "02 · 来源与创作资产", (
        ("source.ingest", "原作导入与证据"),
        ("source.characters", "人物与世界资产"),
        ("source.style", "作品文风"),
    )),
    ("planning", "03 · 长篇规划", (
        ("planning.story", "故事架构、章节与场景清单"),
    )),
    ("scene", "04 · 场景创作", (
        ("scene.entry", "入场、事实与主创意图"),
        ("scene.actor", "角色推演器"),
        ("scene.environment", "环境描写 agent"),
        ("scene.character", "人物描写器"),
        ("scene.event", "事件叙述器：场外与设定"),
        ("scene.frame", "场面描写器"),
        ("scene.observation", "描写器共用合同"),
        ("scene.selection", "候选取舍与构图"),
        ("scene.prose", "正文成稿"),
        ("scene.review", "文学审读"),
        ("scene.revision", "修订与交接"),
        ("scene.transport", "自然文本后置整理"),
    )),
    ("audit", "05 · 状态与审计", (
        ("audit.continuity", "连续性与 Canon"),
        ("audit.review", "独立审查与返修"),
    )),
    ("release", "06 · 导出与发布", (
        ("release.tasks", "交付任务"),
    )),
    ("execution", "07 · 正式任务执行结构", (
        ("execution.contract", "任务程序与 Worker 权限"),
        ("execution.context", "证据与阅读边界"),
        ("execution.semantic", "语义与输出合同"),
        ("execution.prose", "正文约束"),
        ("execution.repair", "返修与恢复"),
        ("execution.completion", "完成与控制权交接"),
    )),
)

_STAGE_ORDER = {stage_id: index for index, (stage_id, _) in enumerate(
    stage for _, _, stages in _FLOW for stage in stages
)}
_SCENE_ASSET_STAGES = (
    ((".branch.selection.", ".composition.execute."), "scene.selection"),
    ((".roleplay.", ".branch.execute."), "scene.actor"),
    ((".prose.generate.",), "scene.prose"),
    ((".agent-review.", ".canon-review.", ".composition.review."), "scene.review"),
    ((".revision.",), "scene.revision"),
    ((".continuity-", ".canon-evolve.", ".state-"), "audit.continuity"),
    ((".*.",), "scene.entry"),
)

_V2_SCENE_STAGES = {
    "scene.v2.transport.extractor": "scene.transport",
    "scene.v2.creator.identity": "scene.entry",
    "scene.v2.creator.protocol": "scene.entry",
    "scene.v2.creator.bootstrap": "scene.entry",
    "scene.v2.creator.archive": "scene.entry",
    "scene.v2.creator.sandbox": "scene.entry",
    "scene.v2.creator.delegation": "scene.selection",
    "scene.v2.creator.actor-card": "scene.actor",
    "scene.v2.creator.selection": "scene.selection",
    "scene.v2.creator.create": "scene.prose",
    "scene.v2.creator.revise": "scene.revision",
    "scene.v2.review": "scene.review",
    "scene.v2.review.protocol": "scene.review",
    "scene.v2.material.shared.protocol": "scene.observation",
    "scene.v2.material.output.protocol": "scene.observation",
    "scene.v2.material.actor": "scene.actor",
    "scene.v2.material.environment": "scene.environment",
    "scene.v2.material.character-description": "scene.character",
    "scene.v2.material.event-narration": "scene.event",
    "scene.v2.material.scene-description": "scene.frame",
}


def arrange_prompt_catalog(layers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Place every active layer once; missing mappings fail loudly during catalog load."""

    unique = {row["layer_id"] for row in layers}
    if len(unique) != len(layers):
        raise ValueError("prompt catalog contains duplicate layer IDs")
    staged = [(stage_for_prompt(row), row) for row in layers]
    staged.sort(key=lambda item: (_STAGE_ORDER[item[0]],
                                  item[1]["responsibility"] == "formal-asset", item[1]["layer_id"]))
    rows = [{**row, "flow_stage": stage} for stage, row in staged]
    leaves: dict[str, list[dict[str, str]]] = {stage: [] for stage in _STAGE_ORDER}
    for row in rows:
        leaves[row["flow_stage"]].append({"id": row["layer_id"], "label": row["purpose"],
                                           "layer_id": row["layer_id"]})
    tree = []
    for group_id, group_label, stages in _FLOW:
        children = [{"id": stage_id, "label": label, "count": len(leaves[stage_id]),
                     "children": leaves[stage_id]}
                    for stage_id, label in stages if leaves[stage_id]]
        if children:
            tree.append({"id": group_id, "label": group_label,
                         "count": sum(child["count"] for child in children), "children": children})
    return rows, tree


def stage_for_prompt(row: dict[str, Any]) -> str:
    layer_id = str(row["layer_id"])
    if row["responsibility"] == "formal-asset":
        return _formal_stage(row)
    if layer_id.startswith("project_agent."):
        return "direction.project"
    if layer_id.startswith(("advisor.", "steward.")):
        return "direction.advice"
    if layer_id.startswith("pi.conversation."):
        return "scene.actor"
    if layer_id.startswith("pi.worker."):
        return "execution.contract"
    if layer_id.startswith("scene."):
        return _scene_stage(layer_id)
    if layer_id.startswith(("formal.prompt_program.", "formal.worker_program.",
                            "formal.file-agent-boundaries.")):
        return "execution.contract"
    if layer_id.startswith(("formal.prepared-context.", "formal.context-access.")):
        return "execution.context"
    if layer_id.startswith(("formal.semantic.", "formal.objective.")):
        return "execution.semantic"
    if layer_id.startswith("formal.prose."):
        return "execution.prose"
    if layer_id.startswith(("formal.repair.", "formal.incremental-repair.")):
        return "execution.repair"
    if layer_id.startswith("formal.completion."):
        return "execution.completion"
    raise ValueError(f"prompt layer has no creative flow location: {layer_id}")


def _scene_stage(layer_id: str) -> str:
    if layer_id in _V2_SCENE_STAGES:
        return _V2_SCENE_STAGES[layer_id]
    if layer_id.startswith("scene.describer.character"):
        return "scene.character"
    if layer_id.startswith("scene.describer.event"):
        return "scene.event"
    if layer_id.startswith("scene.describer.scene"):
        return "scene.frame"
    if layer_id.startswith(("scene.describer.", "scene.description.")):
        return "scene.observation"
    if layer_id.startswith(("scene.actor.", "scene.performance.")):
        return "scene.actor"
    if layer_id.startswith("scene.environment."):
        return "scene.environment"
    if layer_id.startswith("scene.review.") or layer_id == "scene.review" or layer_id.startswith("scene.ownership."):
        return "scene.review"
    if layer_id.startswith(("scene.creator.revise", "scene.creator.revision-request")):
        return "scene.revision"
    if layer_id.startswith(("scene.material.", "scene.creator.material-")):
        return "scene.selection"
    if layer_id.startswith(("scene.creator.", "scene.protocol", "scene.fallbacks.",
                            "scene.quantitative_detail.")):
        return "scene.entry"
    raise ValueError(f"scene prompt has no creative flow location: {layer_id}")


def _formal_stage(row: dict[str, Any]) -> str:
    route = str(row.get("route") or "")
    route_stage = {
        "source-ingest": "source.ingest",
        "character-and-world-assets": "source.characters",
        "style-engineering": "source.style",
        "longform-planning": "planning.story",
        "review-and-audit": "audit.review",
        "export-and-release": "release.tasks",
    }
    if route in route_stage:
        return route_stage[route]
    if route != "scene-development":
        raise ValueError(f"formal prompt has unknown creative route: {route}")
    identity = str(row.get("prompt_asset_id") or "")
    stage = next((stage for patterns, stage in _SCENE_ASSET_STAGES
                  if any(pattern in identity for pattern in patterns)), None)
    if stage is not None:
        return stage
    raise ValueError(f"formal scene prompt has no creative flow location: {identity}")
