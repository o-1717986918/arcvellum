"""Pure layered prompt contracts; storage and project selection belong to Studio."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import re
from typing import Iterable

from literary_engineering_studio_engine.foundation.resources import engine_path


@dataclass(frozen=True)
class PromptLayerSpec:
    layer_id: str
    responsibility: str
    purpose: str
    default_text: str
    editable: bool
    owner: str
    package_version: int = 1


@dataclass(frozen=True)
class PromptLayerOverride:
    layer_id: str
    scope: str
    version: int
    text: str


@dataclass(frozen=True)
class ResolvedPromptLayer:
    layer_id: str
    responsibility: str
    purpose: str
    source: str
    version: str
    text: str
    digest: str
    editable: bool

    def manifest(self) -> dict[str, str | bool]:
        return {"layer_id": self.layer_id, "responsibility": self.responsibility,
                "purpose": self.purpose, "source": self.source, "version": self.version,
                "digest": self.digest, "editable": self.editable}


_LAYER_METADATA = (
    ("experiment.less_ai_tone.editor", "stage", "实验 · 主创局部去 AI 味编辑", True, "Studio", 1),
    ("scene.protocol", "protocol", "角色权限、事实边界与正式交付结构", False, "Engine", 1),
    ("scene.creator.identity", "identity", "主创文学使命", True, "Studio", 3),
    ("scene.creator.create", "stage", "成稿与取材", True, "Studio", 4),
    ("scene.creator.revise", "stage", "修订", True, "Studio", 4),
    ("scene.review", "stage", "独立文学审读", True, "Studio", 2),
    ("scene.performance.plan", "stage", "主创表演规划", True, "Engine literary", 1),
    ("scene.actor.identity", "identity", "角色人格初始化附加指引", True, "Engine literary", 1),
    ("scene.actor.turn", "stage", "角色本轮回应", True, "Engine literary", 1),
    ("scene.environment.identity", "identity", "环境观察方式", True, "Engine literary", 1),
    ("scene.environment.turn", "stage", "环境本轮观察", True, "Engine literary", 1),
    ("scene.describer.character", "identity", "人物可见描写", True, "Engine literary", 1),
    ("scene.describer.event", "identity", "场外事件与世界说明叙述", True, "Engine literary", 1),
    ("scene.describer.scene", "identity", "场面描写", True, "Engine literary", 1),
    ("scene.description.turn", "stage", "描写器当轮任务", True, "Engine literary", 1),
    ("scene.material.selection", "stage", "主创对角色与描写候选的取舍", True, "Engine literary", 2),
    ("scene.v2.creator.identity", "identity", "作品级主创人格承接", True, "Studio", 4),
    ("scene.v2.creator.protocol", "protocol", "主创自然创作交流", True, "Studio", 4),
    ("scene.v2.creator.bootstrap", "stage", "必达信息包与来源使用", True, "Studio", 4),
    ("scene.v2.creator.create", "stage", "场景成稿与自主取材", True, "Studio", 4),
    ("scene.v2.creator.revise", "stage", "场景修订与再取材", True, "Studio", 4),
    ("scene.v2.creator.delegation", "stage", "主创编写五类委托", True, "Studio", 4),
    ("scene.v2.creator.actor-card", "stage", "主创填写强风格化角色系统卡", True, "Studio", 4),
    ("scene.v2.creator.archive", "stage", "作品档案读取与挂载", True, "Studio", 4),
    ("scene.v2.creator.sandbox", "stage", "持久沙盒工作方式", True, "Studio", 4),
    ("scene.v2.creator.selection", "stage", "候选取舍与正文重组", True, "Studio", 4),
    ("scene.v2.review", "stage", "新版场景独立审读", True, "Studio", 4),
    ("scene.v2.review.protocol", "protocol", "自然审读信", True, "Studio", 4),
    ("scene.v2.material.shared.protocol", "protocol", "历史共享层（自然链路已退出）", False, "Engine literary", 2),
    ("scene.v2.material.actor", "identity", "角色卡系统提示词模板", True, "Engine literary", 3),
    ("scene.v2.material.environment", "identity", "环境观察委托模板", True, "Engine literary", 4),
    ("scene.v2.material.character-description", "identity", "人物描写委托模板", True, "Engine literary", 4),
    ("scene.v2.material.event-narration", "identity", "事件叙述委托模板", True, "Engine literary", 4),
    ("scene.v2.material.scene-description", "identity", "场面描写委托模板", True, "Engine literary", 4),
    ("scene.v2.material.output.protocol", "protocol", "历史 JSON 候选层（自然链路已退出）", False, "Engine literary", 2),
    ("project_agent.creator_persona.v2", "stage", "顶层生成或更新主创人格", True, "Studio", 4),
    ("scene.v2.transport.extractor", "protocol", "后置整理合同（技术步骤）", True, "Studio", 1),
    ("project_agent.v2.creative_direction", "stage", "自然交流 · creative_direction", True, "Studio", 1),
    ("project_agent.v2.system.read.protocol", "stage", "自然交流 · system.read.protocol", True, "Studio", 1),
    ("project_agent.v2.system.write.protocol", "stage", "自然交流 · system.write.protocol", True, "Studio", 1),
    ("project_agent.v2.turn.protocol", "stage", "自然交流 · turn.protocol", True, "Studio", 1),
    ("project_agent.v2.scene_checkpoint.protocol", "stage", "自然交流 · scene_checkpoint.protocol", True, "Studio", 1),
    ("project_agent.v2.goal_followup.protocol", "stage", "自然交流 · goal_followup.protocol", True, "Studio", 1),
    ("formal.prompt_program.v3", "protocol", "正式任务结构化 IR", False, "Studio", 2),
    ("scene.creator.create.protocol", "protocol", "主创成稿事实与交付模板", False, "Studio", 3),
    ("scene.creator.revise.protocol", "protocol", "主创修订事实与交付模板", False, "Studio", 2),
    ("scene.review.protocol", "protocol", "审读证据与交付模板", False, "Studio", 2),
    ("scene.performance.plan.protocol", "protocol", "人格化规划与输出合同模板", False, "Engine literary", 1),
    ("scene.actor.scene.protocol", "protocol", "角色场景回应模板", False, "Engine literary", 1),
    ("scene.environment.turn.protocol", "protocol", "环境观察输出模板", False, "Engine literary", 1),
    ("scene.actor.interaction.protocol", "protocol", "角色按需取材的逐轮回应模板", False, "Engine literary", 1),
    ("scene.describer.initialization.protocol", "protocol", "描写器人格初始化结构模板", False, "Engine literary", 1),
    ("scene.describer.character.protocol", "protocol", "人物描写的视角与行动边界", False, "Engine literary", 1),
    ("scene.describer.event.protocol", "protocol", "事件说明的事实和读者知识边界", False, "Engine literary", 1),
    ("scene.describer.scene.protocol", "protocol", "场面描写的行动边界", False, "Engine literary", 1),
    ("scene.describer.turn.protocol", "protocol", "描写候选与 JSON 输出合同", False, "Engine literary", 1),
    ("scene.actor.immersion.protocol", "protocol", "角色人格化沉浸约束", False, "Engine literary", 1),
    ("scene.environment.initialization.example", "protocol", "环境人格初始化六区块示例", False, "Engine literary", 1),
    ("advisor.conversation.protocol", "protocol", "只读顾问权限、证据与元数据模板", False, "Studio", 1),
    ("advisor.identity", "identity", "创作顾问的交流方式与文学判断", True, "Studio", 1),
    ("advisor.persona.chief-editor", "identity", "内置严谨总编的人格与文学关注", True, "Studio advisor", 1),
    ("advisor.persona.dramaturg", "identity", "内置戏剧构筑师的人格与文学关注", True, "Studio advisor", 1),
    ("advisor.persona.cold-reader", "identity", "内置冷面读者的人格与文学关注", True, "Studio advisor", 1),
    ("advisor.persona.warm-peer", "identity", "内置温和同行的人格与文学关注", True, "Studio advisor", 1),
    ("advisor.persona.mystery-auditor", "identity", "内置悬疑审计员的人格与文学关注", True, "Studio advisor", 1),
    ("project_agent.creative_direction", "identity", "作品总编的文学方向判断", True, "Studio", 1),
    ("project_agent.system.write.protocol", "protocol", "项目总编写权限、工具与事实边界", False, "Studio", 1),
    ("project_agent.system.read.protocol", "protocol", "项目总编只读权限与事实边界", False, "Studio", 1),
    ("project_agent.turn.protocol", "protocol", "项目总编对话交接", False, "Studio", 1),
    ("project_agent.goal_followup.protocol", "protocol", "长期目标终态交接", False, "Studio", 1),
    ("project_agent.scene_checkpoint.protocol", "protocol", "场间检查点交接", False, "Studio", 1),
    ("pi.conversation.system", "protocol", "无工具角色会话的系统权限边界", False, "Pi Worker", 1),
    ("steward.identity", "identity", "自动决策顾问的文学取舍", True, "Studio", 1),
    ("steward.decision.protocol", "protocol", "自动决策选项权限、证据与 JSON 合同", False, "Studio", 1),
    ("steward.repair.protocol", "protocol", "自动决策 JSON 修复", False, "Studio", 1),
    ("steward.scope.chapter.protocol", "protocol", "单章发布判断范围", False, "Studio", 1),
    ("steward.scope.final.protocol", "protocol", "全书终章判断范围", False, "Studio", 1),
    ("steward.scope.default.protocol", "protocol", "通用授权判断范围", False, "Studio", 1),
    ("scene.quantitative_detail.protocol", "protocol", "场景数词语义与来源核对规则", False, "Studio", 1),
    ("scene.creator.material-final-pass.protocol", "protocol", "主创对已取素材的正文取舍", False, "Studio", 1),
    ("scene.creator.material-length-priority.protocol", "protocol", "素材较少时的叙述空间", False, "Studio", 1),
    ("scene.creator.material-request.protocol", "protocol", "主创首次取材请求结构与角色续演示例", False, "Studio", 2),
    ("scene.creator.material-choice-repair.protocol", "protocol", "主创无效独写理由的取材决策补救", False, "Studio", 1),
    ("scene.creator.material-selection-repair.protocol", "protocol", "主创候选取舍记录补救", False, "Studio", 1),
    ("scene.creator.revision-request.protocol", "protocol", "主创返修取材请求结构", False, "Studio", 1),
    ("scene.review.convergence.normal.protocol", "protocol", "常规审读返修范围", False, "Studio", 1),
    ("scene.review.convergence.strict.protocol", "protocol", "多轮返修后收敛范围", False, "Studio", 1),
    ("scene.performance.plan-repair.protocol", "protocol", "场景规划结构补救", False, "Studio", 1),
    ("scene.actor.turn-repair.protocol", "protocol", "角色本轮结构补救", False, "Studio", 1),
    ("scene.ownership.action-audit.protocol", "protocol", "一级言行来源审查", False, "Studio", 1),
    ("scene.fallbacks.protocol", "protocol", "场景主创、审读和取材的无资料占位及上限说明", False, "Studio", 1),
    ("pi.worker.main-creative.protocol", "protocol", "正式主创 Worker 工具与写入权限", False, "Pi Worker", 1),
    ("pi.worker.incremental-repair.protocol", "protocol", "正式修复 Worker 写入范围", False, "Pi Worker", 1),
    ("pi.worker.generic-role.protocol", "protocol", "通用正式 Worker 工具权限", False, "Pi Worker", 1),
    ("formal.file-agent-boundaries.protocol", "protocol", "文件型 Agent 的证据与写入范围", False, "Studio", 1),
    ("formal.incremental-repair.protocol", "protocol", "正式任务确定性问题的增量修复合同", False, "Studio", 1),
    ("formal.worker_program.v2.protocol", "protocol", "旧正式 Worker 完整任务模板", False, "Studio", 1),
    ("formal.semantic.default.protocol", "protocol", "无语义合同时的任务说明", False, "Studio", 1),
    ("formal.semantic.base.protocol", "protocol", "正式语义成果字段与锁定值", False, "Studio", 1),
    ("formal.semantic.revision.protocol", "protocol", "精准来源修订语义要求", False, "Studio", 1),
    ("formal.semantic.branch.protocol", "protocol", "分支提案语义要求", False, "Studio", 1),
    ("formal.semantic.requirements.protocol", "protocol", "审查通过与返修要求", False, "Studio", 1),
    ("formal.semantic.continuity-delta.protocol", "protocol", "连续性增量语义要求", False, "Studio", 1),
    ("formal.semantic.continuity-review.protocol", "protocol", "连续性独立复核要求", False, "Studio", 1),
    ("formal.prepared-context.protocol", "protocol", "内联上下文证据标识与阅读边界", False, "Studio", 1),
    ("formal.prepared-context.empty.protocol", "protocol", "无内联上下文时的精确阅读指引", False, "Studio", 1),
    ("formal.repair.semantic-contract.protocol", "protocol", "正式返修语义输出合同说明", False, "Studio", 1),
    ("formal.repair.stagnation.protocol", "protocol", "正式返修停滞恢复说明", False, "Studio", 1),
    ("formal.repair.quantitative-reduce.protocol", "protocol", "正式返修字数减量合同", False, "Studio", 1),
    ("formal.repair.quantitative-increase.protocol", "protocol", "正式返修字数增量合同", False, "Studio", 1),
    ("formal.repair.regression-guard.protocol", "protocol", "正式返修跨回合回归防线", False, "Studio", 1),
    ("formal.repair.reasoning-budget.protocol", "protocol", "正式返修推理预算说明", False, "Studio", 1),
    ("formal.repair.session-same.protocol", "protocol", "同会话返修状态", False, "Studio", 1),
    ("formal.repair.session-independent.protocol", "protocol", "独立返修状态", False, "Studio", 1),
    ("formal.repair.regression-range.protocol", "protocol", "返修字数回归范围", False, "Studio", 1),
    ("formal.repair.regression-budget.protocol", "protocol", "返修预算保持要求", False, "Studio", 1),
    ("formal.repair.regression-increase.protocol", "protocol", "字数缺口时的回归策略", False, "Studio", 1),
    ("formal.repair.regression-replace.protocol", "protocol", "无字数缺口时的回归策略", False, "Studio", 1),
    ("formal.repair.invalid-empty.protocol", "protocol", "无可映射返修片段说明", False, "Studio", 1),
    ("formal.repair.targets-empty.protocol", "protocol", "无可映射返修目标说明", False, "Studio", 1),
    ("formal.completion.empty-output.protocol", "protocol", "正式任务没有创作文件时的清单说明", False, "Studio", 1),
    ("formal.completion.pass-conclusion.protocol", "protocol", "正式审查必须通过的机器行", False, "Studio", 1),
    ("formal.completion.recorded-conclusion.protocol", "protocol", "正式审查必须记录的机器行", False, "Studio", 1),
    ("formal.completion.stop.protocol", "protocol", "正式任务完成后的控制权交接", False, "Studio", 1),
    ("formal.completion.required-read.protocol", "protocol", "正式任务首轮阅读要求", False, "Studio", 1),
    ("formal.completion.on-demand-read.protocol", "protocol", "正式任务按需精读要求", False, "Studio", 1),
    ("formal.completion.empty-read.protocol", "protocol", "正式任务无额外阅读说明", False, "Studio", 1),
    ("formal.completion.output-line.protocol", "protocol", "正式任务输出文件清单行", False, "Studio", 1),
    ("formal.completion.empty-checks.protocol", "protocol", "正式任务无额外检查时的条件", False, "Studio", 1),
    ("formal.context-access.none.protocol", "protocol", "没有受保护输出时的阅读说明", False, "Studio", 1),
    ("formal.context-access.unclassified.protocol", "protocol", "未分类受保护输出的阅读要求", False, "Studio", 1),
    ("formal.context-access.recovery.protocol", "protocol", "精确按需恢复证据的阅读限制", False, "Studio", 1),
    ("formal.context-access.prepared.protocol", "protocol", "已内联受保护输出的阅读说明", False, "Studio", 1),
    ("formal.prose.budget.protocol", "protocol", "正式场景正文的字数预算与篇幅分配", False, "Studio", 1),
    ("formal.prose.budget-short.protocol", "protocol", "无明确预算的当前场景边界", False, "Studio", 1),
    ("formal.prose.scope.protocol", "protocol", "正式正文任务与资产任务职责边界", False, "Studio", 1),
    ("formal.prose.manifest.protocol", "protocol", "候选 manifest 的模型字段边界", False, "Studio", 1),
    ("formal.prose.stop.protocol", "protocol", "正式任务完成与阻断合同", False, "Studio", 1),
    ("formal.objective.user-direction.protocol", "protocol", "正式任务用户方向标题", False, "Studio", 1),
    ("formal.objective.empty.protocol", "protocol", "正式任务正文为空时的默认说明", False, "Studio", 1),
    ("advisor.snapshot-readme.protocol", "protocol", "顾问只读资料快照的信任边界", False, "Studio", 1),
)


def _default_text(layer_id: str) -> str:
    return engine_path("templates", "prompt_layers", f"{layer_id}.md").read_text(encoding="utf-8").strip()


_SPECS = tuple(PromptLayerSpec(layer_id, responsibility, purpose, _default_text(layer_id),
                               editable, owner, version)
               for layer_id, responsibility, purpose, editable, owner, version in _LAYER_METADATA)


def list_prompt_layer_specs() -> tuple[PromptLayerSpec, ...]:
    return _SPECS


def prompt_layer_spec(layer_id: str) -> PromptLayerSpec:
    try:
        return next(spec for spec in _SPECS if spec.layer_id == layer_id)
    except StopIteration as exc:
        raise ValueError(f"unknown prompt layer: {layer_id}") from exc


@lru_cache(maxsize=1)
def _scene_fallbacks() -> dict[str, str]:
    raw = json.loads(prompt_layer_spec("scene.fallbacks.protocol").default_text)
    if not isinstance(raw, dict) or not all(isinstance(key, str) and isinstance(value, str) and value.strip()
                                            for key, value in raw.items()):
        raise ValueError("scene prompt fallback registry is invalid")
    return raw


def scene_prompt_fallback(key: str) -> str:
    """Return a registered fixed fallback for absent runtime scene data."""
    try:
        return _scene_fallbacks()[key]
    except KeyError as exc:
        raise ValueError(f"unknown scene prompt fallback: {key}") from exc


_TEMPLATE_SLOT = re.compile(r"\[\[ARCVELLUM_PROMPT_([0-9]+)\]\]")


def render_prompt_template(layer_id: str, values: tuple[object, ...]) -> str:
    """Render a registered fixed protocol template without interpreting injected data."""
    spec = prompt_layer_spec(layer_id)
    if spec.responsibility != "protocol" or spec.editable:
        raise ValueError("prompt template must be a fixed protocol layer")
    template = engine_path("templates", "prompt_layers", f"{layer_id}.md").read_text(encoding="utf-8")
    return render_prompt_text(template, values)


def render_prompt_text(template: str, values: tuple[object, ...]) -> str:
    """Fill validated slots in editable prose without recursively interpreting data."""
    indexes = {int(match.group(1)) for match in _TEMPLATE_SLOT.finditer(template)}
    if indexes != set(range(len(values))):
        raise ValueError("prompt template slots do not match supplied values")
    return _TEMPLATE_SLOT.sub(lambda match: str(values[int(match.group(1))]), template)


def resolve_prompt_layer(
    spec: PromptLayerSpec, *, global_override: PromptLayerOverride | None = None,
    project_override: PromptLayerOverride | None = None,
) -> ResolvedPromptLayer:
    if not spec.editable and (global_override or project_override):
        raise ValueError("protocol and dynamic prompt layers cannot be overridden")
    choice = project_override or global_override
    if choice is not None:
        expected_scope = "project" if project_override is not None else "global"
        if choice.layer_id != spec.layer_id or choice.scope != expected_scope or choice.version < 1:
            raise ValueError("prompt override does not match layer and scope")
        text, source, version = choice.text, choice.scope, str(choice.version)
    else:
        text, source, version = spec.default_text, "package", str(spec.package_version)
    if not text.strip() or len(text) > 12_000:
        raise ValueError("prompt layer text must be nonempty and bounded")
    return ResolvedPromptLayer(spec.layer_id, spec.responsibility, spec.purpose, source, version,
                               text, hashlib.sha256(text.encode("utf-8")).hexdigest(), spec.editable)


def prompt_assembly_manifest(layers: Iterable[ResolvedPromptLayer]) -> dict[str, object]:
    entries = [layer.manifest() for layer in layers]
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"schema": "arcvellum/prompt-assembly/v1", "layers": entries, "digest": digest}
