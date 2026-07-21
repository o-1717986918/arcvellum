from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from shutil import copyfile

from .creative_quality import default_creative_quality_profile
from .resources import engine_root


@dataclass(frozen=True)
class InitOptions:
    target: Path
    title: str
    work_type: str = "novel"
    target_length: int = 30000
    language: str = "zh-CN"
    premise: str = ""
    genre: str = ""
    style_mode: str = "public_domain_or_authorized"


@dataclass(frozen=True)
class InitResult:
    root: Path
    files: tuple[Path, ...]


def _repo_root() -> Path:
    return engine_root()


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _write(path: Path, content: str, files: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    files.append(path)


def _copy_template(template_name: str, target: Path, files: list[Path]) -> None:
    src = _repo_root() / "templates" / template_name
    target.parent.mkdir(parents=True, exist_ok=True)
    copyfile(src, target)
    files.append(target)


def _project_yaml(options: InitOptions) -> str:
    return f"""project:
  title: {_quote(options.title)}
  type: {options.work_type}
  target_length: {options.target_length}
  language: {options.language}
  status: planning
  created_at: {_quote(datetime.now(timezone.utc).isoformat())}

creative_brief:
  premise: {_quote(options.premise)}
  genre: {_quote(options.genre)}
  audience: ""
  central_question: ""
  themes: []
  forbidden_elements: []

longform_budget:
  target_words: {options.target_length}
  volumes: 0
  status: pending_word_budget
  note: "正式长篇生成前运行 word-budget / longform-budget，并由平台 Agent 处理预算化大纲任务。"

style:
  mode: {options.style_mode}
  target_profiles: []
  blend_strategy: ""

generation:
  default_provider: auto
  prompt_templates:
    system: prompts/scene_generation_system.md
    user: prompts/scene_generation_user.md
  model_env:
    global_config: ~/.lew/config.json
    api_base: LEW_MODEL_API_BASE
    api_key: LEW_MODEL_API_KEY
    model_name: LEW_MODEL_NAME

workflow:
  require_human_approval_for:
    - confirmed_canon
    - major_character_turn
    - main_plot_branch_merge
    - final_export

quality_gates:
  canon_test: required
  character_test: required
  plot_test: required
  style_test: required
  originality_test: required
"""


def _agents_md(title: str) -> str:
    return f"""# Agent 入口：{title}

本目录是一部具体作品的文学工程项目。Agent 接手时必须先读：

1. `project.yaml`
2. `agentread.yaml`
3. `canon/world_rules.yaml`
4. `characters/_template.yaml`
5. `plot/outline.md`
6. `style/style-profile.md`
7. `prompts/scene_generation_system.md`
8. `prompts/scene_generation_user.md`

## 工作原则

- 正文生成前先构建场景上下文包。
- 模型生成必须使用 prompts 下的版本化提示词模板。
- 软记忆召回不能覆盖 canon。
- 新事实必须先进入候选区，再由人工确认。
- 角色推演必须基于人物 BDI。
- 每个角色单独维护在 `characters/{{character_id}}.yaml`；`importance: major` 的主要角色常驻上下文，次要角色只在场景 `participants`、`referenced_characters` 或 `character_refs` 命中时完整载入。
- 可挂载文风 `prompt.md` 必须是 500-2500 中文内容字符的高质量 LLM 提示词，计入汉字和中文标点，不计入 Markdown 标记、英文路径、代码围栏或空白，并包含身份/边界、优先级、核心机制、叙述距离、句法节奏、标点、意象感官、心理行为、对白语气、禁止倾向和自检。
- 中长篇或百万字级目标必须先运行 `word-budget` / `longform-budget`，把目标中文内容字符拆成卷、章、场景和叙事负载；预算化大纲候选通过平台 Agent 审查前，不得批量生成正文。
- 中长篇 scene-development 正文生成前必须完成 `chapter-obligation`：每章建立章节义务、读者问题、承诺回报、暂扣信息、兑现/延迟、反摘要要求和读后余味契约。
- 正文生成和审查要降低 AI 腔：机械“不是……而是……”及“不是……——是……”等变体是核心禁区，不判断为合理修辞；器官轮岗、万能占位、比喻依赖、抽象总结、解释性心理标签、模板化转折、对称排比、景物强制同步和金句化结尾按约 2% 叙事单元密度门禁控制。
- 从已有文本反推设定时，必须先写入 `sources/imports/` 和候选区，由平台 Agent 提取并审查，不得直接写入正式 canon、characters 或 plot。
- 审查未通过的草稿不能进入正稿。

## 默认流程

```text
读取项目状态 -> 构建场景上下文包 -> 角色推演 -> 分支推演 -> 场景编排 -> 候选生成 -> 审查 -> 写回候选 -> 人工确认
```
"""


def _agentread_yaml() -> str:
    return """schema: literary-work-project/v0.1
read_first:
  - AGENTS.md
  - project.yaml
  - canon/world_rules.yaml
  - plot/outline.md
task_routes:
  create_scene:
    read:
      - project.yaml
      - canon/world_rules.yaml
      - canon/timeline.yaml
      - characters/_template.yaml
      - plot/outline.md
      - style/style-profile.md
      - scenes/scene_0001.yaml
  review_draft:
    read:
      - canon/facts.json
      - characters/_template.yaml
      - plot/foreshadowing.csv
      - style/style-profile.md
      - reviews/review-report-template.md
  update_canon:
    read:
      - canon/facts.json
      - canon/timeline.yaml
      - reviews/
  source_ingest:
    read:
      - sources/imports/
      - canon/
      - characters/
      - plot/
      - style/
      - reviews/source_ingest/
  longform_planning:
    read:
      - project.yaml
      - plot/outline.md
      - plot/word_budget/
      - plot/chapter_obligations/
      - scenes/
      - reviews/word_budget/
"""


def init_work_project(options: InitOptions) -> InitResult:
    root = options.target.resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"target directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)

    files: list[Path] = []

    _write(root / "project.yaml", _project_yaml(options), files)
    _write(
        root / "style" / "creative_quality_profile.json",
        json.dumps(default_creative_quality_profile(), ensure_ascii=False, indent=2) + "\n",
        files,
    )
    _write(root / "AGENTS.md", _agents_md(options.title), files)
    _write(root / "agentread.yaml", _agentread_yaml(), files)

    _write(root / "canon" / "world_rules.yaml", "rules: []\nconstraints: []\nopen_questions: []\n", files)
    _write(root / "canon" / "timeline.yaml", "events: []\n", files)
    _write(
        root / "canon" / "facts.json",
        json.dumps({"facts": [], "conflicts": [], "candidates": []}, ensure_ascii=False, indent=2) + "\n",
        files,
    )
    _write(root / "canon" / "locations.yaml", "locations: []\n", files)
    _write(root / "canon" / "organizations.yaml", "organizations: []\n", files)
    _write(root / "canon" / "forbidden_changes.yaml", "forbidden_changes: []\n", files)
    _write(root / "canon" / "candidates" / "world_rules" / "README.md", "# world rule candidates\n\nAgent 生成的世界观候选放在这里。不得直接作为 confirmed canon。\n", files)
    _write(root / "canon" / "candidates" / "locations" / "README.md", "# location candidates\n\nAgent 生成的地点候选放在这里。\n", files)
    _write(root / "canon" / "candidates" / "organizations" / "README.md", "# organization candidates\n\nAgent 生成的组织候选放在这里。\n", files)
    _write(root / "canon" / "candidates" / "extracted" / "README.md", "# extracted canon candidates\n\n从已有作品反推的世界观、地点、组织和规则候选放在这里。必须带证据引用和置信度。\n", files)

    _copy_template("character.yaml", root / "characters" / "_template.yaml", files)
    _write(root / "characters" / "candidates" / "README.md", "# character candidates\n\nAgent 生成的人物候选放在这里。未经 review 和 approve，不得晋升为正式人物档案。\n", files)
    _write(root / "characters" / "candidates" / "background_stories" / "README.md", "# background story candidates\n\nAgent 生成的人物背景故事候选放在这里。背景故事只作为隐性行为因果。\n", files)
    _write(root / "characters" / "candidates" / "extracted" / "README.md", "# extracted character candidates\n\n从已有作品反推的人物、关系、BDI 和背景故事候选放在这里。\n", files)
    _write(root / "characters" / "state_patches" / "README.md", "# state_patches\n\n人物状态演化候选 patch 放在这里。未经人工确认，不得写回人物档案。\n", files)
    _copy_template("scene.yaml", root / "scenes" / "scene_0001.yaml", files)
    _copy_template("style/style-profile.md", root / "style" / "style-profile.md", files)
    _copy_template("review-report.md", root / "reviews" / "review-report-template.md", files)
    _write(root / "reviews" / "longform" / "README.md", "# longform\n\n长篇连续性审计报告放在这里。\n", files)
    _write(root / "reviews" / "word_budget" / "README.md", "# word_budget\n\n长篇字数预算、剧情库存和预算化大纲审查报告放在这里。\n", files)

    _write(root / "plot" / "outline.md", f"# {options.title} 大纲\n\n## Premise\n\n{options.premise or '尚未填写。'}\n", files)
    _write(root / "plot" / "word_budget" / "README.md", "# word_budget\n\n运行 `word-budget` / `longform-budget` 后，预算报告、JSON 和平台 Agent 任务侧车放在这里。\n", files)
    _write(root / "plot" / "chapter_obligations" / "README.md", "# chapter_obligations\n\n运行 `chapter-obligation` 后，每章的承诺、兑现/延迟和逐场读者体验契约放在这里。\n", files)
    _write(root / "plot" / "candidates" / "outlines" / "README.md", "# outline candidates\n\nAgent 生成的大纲、章节计划和场景列表候选放在这里。\n", files)
    _write(root / "plot" / "candidates" / "relationships" / "README.md", "# relationship candidates\n\nAgent 生成的人物关系网候选放在这里。\n", files)
    _write(root / "plot" / "candidates" / "extracted" / "README.md", "# extracted plot candidates\n\n从已有作品反推的大纲、时间线、伏笔和未解问题候选放在这里。\n", files)
    _write(root / "plot" / "scene_graph.json", json.dumps({"scenes": [], "edges": []}, ensure_ascii=False, indent=2) + "\n", files)
    _write(root / "plot" / "longform_graph.json", json.dumps({"nodes": [], "edges": []}, ensure_ascii=False, indent=2) + "\n", files)
    _write(root / "plot" / "chapters" / "README.md", "# chapters\n\n章节级状态 JSON 放在这里。\n", files)
    _write(root / "plot" / "foreshadowing.csv", "foreshadow_id,setup_scene,visibility,expected_payoff,status,notes\n", files)
    _write(root / "plot" / "conflict_matrix.md", "# 冲突矩阵\n\n| 角色/势力 | 目标 | 冲突对象 | 代价 |\n| --- | --- | --- | --- |\n", files)

    _write(root / "drafts" / "README.md", "# drafts\n\n正文草稿和正稿版本放在这里。\n", files)
    _write(root / "drafts" / "chapters" / "README.md", "# chapters\n\n章节级工作台和章节草稿放在这里。\n", files)
    _write(root / "memory" / "README.md", "# memory\n\n向量索引、摘要和检索日志放在这里。\n", files)
    _write(root / "memory" / "retrieval_logs" / "README.md", "# retrieval_logs\n\n每次生成前的检索记录放在这里。\n", files)
    _write(root / "memory" / "context_packets" / "README.md", "# context_packets\n\n场景上下文包和 `.trace.json` 来源证明放在这里。正式 scene-development 必须同时具备 context packet 与 context trace。\n", files)
    _write(root / "sources" / "README.md", "# sources\n\n已有文本、完整作品、改写/续写源材料的导入清单放在这里。使用 `source-ingest` 生成 `imports/{work_id}/` 后，由平台 Agent 反推候选设定。\n", files)
    _write(root / "sources" / "imports" / "README.md", "# imports\n\n每次导入一个已有作品或源文本，生成 raw、chunks、manifest、report 和平台 Agent 提取任务。\n", files)
    _write(root / "style" / "candidates" / "README.md", "# style candidates\n\n从已有文本或作品反推的可生成文风说明候选放在这里。正式挂载前应转化为合格 Style Skill。\n", files)
    _write(root / "reviews" / "source_ingest" / "README.md", "# source_ingest reviews\n\n已有作品反推设定的证据强度、矛盾、缺漏和晋升建议审查放在这里。\n", files)
    _write(root / "branches" / "README.md", "# branches\n\n剧情分支实验放在这里。\n", files)
    _write(root / "agents" / "runs" / "README.md", "# agent runs\n\n通用 Agent 输入输出、schema validation 和 repair attempts 放在这里。\n", files)
    _write(root / "agents" / "patch_plans" / "README.md", "# patch plans\n\nAgent 生成的受控写回计划放在这里。未经审批不得直接应用。\n", files)
    _write(root / "agents" / "committee" / "README.md", "# committee\n\n多 Agent 审稿委员会的独立意见和汇总结果放在这里。\n", files)
    _copy_template("prompts/scene_generation_system.md", root / "prompts" / "scene_generation_system.md", files)
    _copy_template("prompts/scene_generation_user.md", root / "prompts" / "scene_generation_user.md", files)
    _write(root / "prompts" / "video_prompt_template.md", "# 视频提示词模板\n\n待后期根据场景状态生成。\n", files)
    _write(root / "exports" / "README.md", "# exports\n\n最终导出文件放在这里。\n", files)
    _write(root / "exports" / "video_prompts" / "README.md", "# video_prompts\n\n视频提示词包可复制或归档到这里。\n", files)
    _write(root / "exports" / "screenplays" / "README.md", "# screenplays\n\n剧本格式导出可复制或归档到这里。\n", files)
    _write(root / "exports" / "chapters" / "README.md", "# chapters\n\n小说章节导出可复制或归档到这里。\n", files)
    _write(root / "releases" / "README.md", "# releases\n\n通过 publish-chapter 生成的发布版本放在这里。\n", files)
    _write(root / "workflow" / "runs" / "README.md", "# workflow runs\n\nAgent 工作流运行状态和日志放在这里。\n", files)
    _write(root / "tests" / "README.md", "# tests\n\n作品级审查和回归测试放在这里。\n", files)

    return InitResult(root=root, files=tuple(files))
