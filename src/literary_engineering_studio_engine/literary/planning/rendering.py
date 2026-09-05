"""Human-readable budget reports and platform-agent sidecar task rendering."""

from __future__ import annotations

from pathlib import Path

from ...agent_tasks import write_agent_tasks
from .common import _rel
from .contracts import load_word_budget_summary, scene_word_budget_contract

def render_word_budget_generation_standard(root: Path) -> str:
    summary = load_word_budget_summary(root)
    if not summary:
        return """# 长篇字数预算标准

当前项目尚未生成 `plot/word_budget/word_budget.json`。若目标是中长篇或百万字级项目，进入正式大纲、章节或场景生成前应先运行 `word-budget`，把总字数拆成卷、章、场景和叙事负载。"""
    target = summary.get("target", {})
    totals = summary.get("totals", {})
    binding = summary.get("scene_inventory_binding", {})
    binding = binding if isinstance(binding, dict) else {}
    underbuilt = binding.get("underbuilt_chapter_count", 0)
    missing_scenes = binding.get("missing_scene_count", 0)
    shortfall = binding.get("word_shortfall", 0)
    return f"""# 长篇字数预算标准

已加载 `{summary.get("path", "")}`。生成和扩写必须遵守以下预算，不得把大纲压缩成剧情摘要：

- 目标中文内容字符：{target.get("target_chinese_chars", target.get("target_words", 0))}
- 卷数：{target.get("volumes", 0)}
- 类型：{target.get("genre_label", target.get("genre", ""))}
- 目标章节数：{totals.get("chapter_count", 0)}
- 目标场景数：{totals.get("scene_count", 0)}
- 平均章中文内容字符：{totals.get("avg_chapter_words", 0)}
- 平均场景中文内容字符：{totals.get("avg_scene_words", 0)}
- 欠账章节数：{underbuilt}
- 缺失场景数：{missing_scenes}
- 正文缺口：{shortfall}

场景生成前必须确认当前场景承担明确叙事负载：主线行动、关系压力、世界/信息释放、行动后果或节奏调节。若 `scene_inventory_binding` 显示当前章节欠场景或正文缺口，先处理 `scene_inventory_expansion.agent_tasks.md`，补候选场景和因果链，不要用长段总结、空泛抒情或重复心理解释灌字数。"""

def render_scene_word_budget_contract(
    root: Path,
    scene_path: Path,
    *,
    materialization_scope: str = "full",
) -> str:
    contract = scene_word_budget_contract(root, scene_path, materialization_scope=materialization_scope)
    status = contract.get("status", "")
    if status == "not_required":
        return "本项目当前未达到强制长篇预算规模；仍应避免把剧情量压缩成摘要或用空泛描写灌字数。"
    if status != "pass":
        return f"本场景字数预算门禁未通过：{contract.get('message')}"
    return "\n".join(
        [
            f"- 场景：{contract.get('scene_id')}",
            f"- 章节：{contract.get('chapter_id')}",
            f"- 目标中文内容字符：{contract.get('target_chinese_chars')}",
            f"- 最低中文内容字符：{contract.get('min_chinese_chars')}",
            f"- 最高中文内容字符：{contract.get('max_chinese_chars')}",
            f"- 机器非空白字符诊断基准：{contract.get('machine_count_mapping', {}).get('rough_expected_machine_chars', contract.get('target_words'))}",
            f"- 机器非空白粗略范围：{contract.get('machine_count_mapping', {}).get('rough_expected_machine_chars_range', [])}",
            f"- 机器映射依据：{contract.get('machine_count_mapping', {}).get('mapping_basis', '')}",
            f"- 目标来源：{contract.get('source') or 'unknown'}",
            f"- scene.yaml 显式目标：{contract.get('scene_yaml_target_words') or 0}",
            f"- 预算推导目标：{contract.get('derived_target_words') or 0}",
            f"- 叙事负载：{', '.join(str(item) for item in contract.get('narrative_load', []))}",
            f"- 预算来源：{contract.get('budget_path')}",
            f"- 对齐状态：{contract.get('alignment_status') or 'n/a'}",
        ]
    )

def _write_agent_tasks(root: Path, markdown_path: Path, json_path: Path, outline_path: Path, task_path: Path, payload: dict) -> None:
    candidate = payload["candidate_outputs"]["budgeted_outline_candidate"]
    source_paths = [markdown_path, json_path, root / "project.yaml"]
    if outline_path.exists():
        source_paths.append(outline_path)
    write_agent_tasks(
        task_path,
        title="longform word budget and narrative inventory review",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是长篇字数预算与剧情库存门禁任务。",
            "CLI 只负责计算预算、统计现有大纲库存和生成诊断；本任务只完成卷章级创意分配，逐场景库存由后续 scene-inventory 正式任务完成。",
            "预算不等于灌字数。补足字数必须通过因果链、场景功能、人物状态、信息释放和行动后果增加剧情库存。",
            "候选大纲未经审查和用户批准，不得覆盖 plot/outline.md 或正式 scene 文件。",
        ],
        tasks=[
            (
                "审查预算与类型映射",
                """读取 word_budget.json / word_budget.md，确认目标中文内容字符、卷数、类型、时间跨度、章节数、场景数和平均场景中文内容字符是否适合该作品。若类型或时间跨度导致节奏不合理，提出修正预算而不是直接缩水。""",
            ),
            (
                "补足剧情库存候选",
                f"""创建或覆盖 `{candidate}`。按卷 -> 章列出可支撑目标中文内容字符的候选骨架。每章必须包含目标中文内容字符、计划场景数、章节功能、关键转向、主线/副线/人物线/世界信息/后果负载、详略等级、读者义务以及承接的前后因果。不要在本任务展开逐场景清单；逐场景功能、目标字符和承接关系由后续 scene-inventory 任务生成，避免重复生成数百条场景后因末端格式问题整单重跑。""",
            ),
            (
                "建立字数-剧情量映射",
                """为每卷写出剧情库存说明：核心事件数、调查/行动链数、人物关系变化数、信息释放点、失败/代价点、伏笔设置和回收点，并给出计划章节数与计划场景总数。若某卷目标约10万字，场景库存通常应达到60-90个；不足时必须标注 underbuilt，但不要在这里逐条创作全部场景。""",
            ),
        ],
    )

def _write_scene_inventory_agent_tasks(root: Path, markdown_path: Path, json_path: Path, outline_path: Path, task_path: Path, payload: dict) -> None:
    candidate = payload["candidate_outputs"]["scene_inventory_expansion"]
    totals = payload["totals"]
    chapter_contract = "；".join(
        f"{row['chapter_id']}={row['scene_count']}场/{row['target_words']}中文内容字符"
        for row in payload["chapter_budgets"]
    )
    source_paths = [markdown_path, json_path, root / "project.yaml", root / "scenes"]
    if outline_path.exists():
        source_paths.append(outline_path)
    write_agent_tasks(
        task_path,
        title="longform scene inventory expansion",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是字数预算到场景库存的绑定任务。",
            "CLI 已计算每章目标中文内容字符、目标场景数、实际 scene 文件数、已写正文中文内容字符、机器非空白字符诊断、缺失场景数和正文缺口。",
            "平台 agent 必须把缺口转化为新场景候选、关系转折、信息释放、行动后果和伏笔链，不得用灌水描写填字数。",
            f"本次精确库存合同：全书必须恰好 {totals['scene_count']} 场、目标合计恰好 {totals['target_chinese_chars']} 中文内容字符；{chapter_contract}。",
            "用户显式 target_scenes 与当前 word_budget.json 是硬约束。若创作判断确需改变场景数，先请求重做预算或记录获批的重新规划，不得在本任务擅自增减。",
            "候选场景列表未经审查和用户批准，不得直接写入 scenes/ 或覆盖 plot/outline.md。",
        ],
        tasks=[
            (
                "读取欠账章节",
                """读取 word_budget.json 的 `scene_inventory_binding.chapter_rows`。筛出 status 为 underbuilt / missing_scenes / word_shortfall 的章节，确认每章缺几个场景、缺多少正文字符、缺哪类叙事负载。""",
            ),
            (
                "生成扩场景候选",
                f"""创建或覆盖 `{candidate}`。这是后续物化正式 scenes/*.yaml 的机器可读合同，不是自由散文清单。必须恰好写 {totals['scene_count']} 个场景，目标字符合计恰好 {totals['target_chinese_chars']}；逐章严格满足：{chapter_contract}。每章先写 `### Ch 0001 — 章节名 |`，随后使用 11 列 Markdown 表格：`| SC-001 | 场景名 | 目标中文内容字符 | 功能 | 参与角色 | 冲突 | 信息释放 | 行动后果 | 伏笔设置/回收 | 节奏角色 | 读者义务 |`。一行对应一个独立场景，SC 编号从 SC-001 开始全书连续且唯一、目标为整数。修订旧候选时必须原位替换错误行并删除重复行，禁止在末尾追加修正版；不得拆成逐场景的说明卡、段落或只含字段/内容的二列表格。不得只写“增加描写”。""",
            ),
        ],
    )

def _write_chapter_obligation_plan_tasks(root: Path, markdown_path: Path, json_path: Path, outline_path: Path, task_path: Path, payload: dict) -> None:
    source_paths = [markdown_path, json_path, root / "project.yaml", root / "scenes"]
    if outline_path.exists():
        source_paths.append(outline_path)
    write_agent_tasks(
        task_path,
        title="longform chapter obligation and reader-experience planning",
        root=root,
        source_paths=source_paths,
        notes=[
            "这是从字数预算进入正文生成前的章节义务总规划任务。",
            "CLI 已给出 chapter_budgets 和 scene_inventory_binding，但读者问题、章节承诺、悬念兑现和反摘要要求必须由平台 Agent 判断。",
            "每个长篇章节正式生成前，还应运行 chapter-obligation --chapter-id <chapter_id> 生成单章契约侧车并完成 marker。",
        ],
        tasks=[
            (
                "建立章节承诺表",
                """读取 word_budget.json 的 chapter_budgets。按每章建立一行章节义务：chapter_id、目标中文内容字符、目标场景数、chapter_function、must_payoff、must_setup、must_change、must_not_resolve、inherited_hooks、ending_hook、inventory_sufficiency、expansion_needed。""",
            ),
            (
                "建立读者体验规划",
                """为每章列出读者将带着什么问题进入、期望什么回报、哪些信息暂扣、哪些承诺本章兑现、哪些必须延迟到后文。重点检查剧情库存是否支撑目标中文内容字符；不足时补事件链、关系压力、信息释放和后果，而不是要求正文灌水。""",
            ),
        ],
    )

def _render_markdown(root: Path, payload: dict, json_path: Path) -> str:
    target = payload["target"]
    totals = payload["totals"]
    inventory = payload["outline_inventory"]
    lines = [
        "# 长篇字数预算与剧情库存报告",
        "",
        f"- JSON：`{_rel(json_path, root)}`",
        f"- 状态：`{payload['status']}`",
        f"- 目标中文内容字符：{target['target_chinese_chars']}",
        "- 计数口径：清洗后中文正文字符，计入汉字和中文标点；机器非空白字符仅作为诊断映射。",
        f"- 卷数：{target['volumes']}",
        f"- 类型：{target['genre_label']}",
        f"- 时间跨度：{target.get('time_span') or '未指定'}",
        f"- 预算章节：{totals['chapter_count']}",
        f"- 预算场景：{totals['scene_count']}",
        f"- 平均章中文内容字符：{totals['avg_chapter_words']}",
        f"- 平均场景中文内容字符：{totals['avg_scene_words']}",
        "",
        "## 卷级预算",
        "",
        "| 卷 | 目标中文内容字符 | 章节 | 场景 | 章均中文内容字符 | 场景均中文内容字符 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload["volume_budgets"]:
        lines.append(
            f"| {item['volume_id']} | {item['target_words']} | {item['chapter_count']} | {item['scene_count']} | {item['avg_chapter_words']} | {item['avg_scene_words']} |"
        )
    lines.extend(
        [
            "",
            "## 章节-场景预算绑定",
            "",
            f"- 欠账章节：{payload['scene_inventory_binding']['underbuilt_chapter_count']}",
            f"- 缺失场景：{payload['scene_inventory_binding']['missing_scene_count']}",
            f"- 正文缺口：{payload['scene_inventory_binding']['word_shortfall']}",
            f"- 已有 scene 文件：{payload['scene_inventory_binding']['actual_scene_count']}",
            f"- 已有清洗后正文字符：{payload['scene_inventory_binding']['actual_draft_chars']}",
            "",
            "| 章节 | 卷 | 目标中文内容字符 | 目标场景 | 已有场景 | 已有正文中文内容字符 | 缺场景 | 正文缺口 | 状态 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["scene_inventory_binding"]["chapter_rows"][:40]:
        lines.append(
            "| {chapter} | {volume} | {target} | {target_scenes} | {actual_scenes} | {actual_chars} | {missing_scenes} | {shortfall} | {status} |".format(
                chapter=row["chapter_id"],
                volume=row["volume_id"],
                target=row["target_words"],
                target_scenes=row["target_scene_count"],
                actual_scenes=row["actual_scene_count"],
                actual_chars=row["actual_draft_chars"],
                missing_scenes=row["missing_scene_count"],
                shortfall=row["word_shortfall"],
                status=row["status"],
            )
        )
    if len(payload["scene_inventory_binding"]["chapter_rows"]) > 40:
        lines.append("| ... | ... | ... | ... | ... | ... | ... | ... | 仅显示前 40 行，完整数据见 JSON |")
    lines.extend(
        [
            "",
            "## 现有大纲库存",
            "",
            f"- 大纲：`{inventory.get('outline_path') or 'missing'}`",
            f"- 已规划卷：{inventory['planned_volume_count']}",
            f"- 已规划章：{inventory['planned_chapter_count']}",
            f"- 大纲场景标记：{inventory['outline_scene_markers']}",
            f"- scene 文件：{inventory['scene_file_count']}",
            f"- 估算场景库存：{inventory['planned_scene_count']}",
            "",
            "## 风险",
            "",
        ]
    )
    if payload["issues"]:
        for issue in payload["issues"]:
            lines.append(f"- **{issue['severity']} / {issue['category']}**：{issue['message']} 建议：{issue['recommendation']}")
    else:
        lines.append("- 未发现明显字数-剧情库存风险。")
    lines.extend(
        [
            "",
            "## 标准链路",
            "",
            "1. 先用本预算确认卷、章、场景和叙事负载。",
            "2. 平台 Agent 根据 `word_budget.agent_tasks.md` 生成预算化大纲候选。",
            "3. 平台 Agent 根据 `scene_inventory_expansion.agent_tasks.md` 补足欠账章节的场景候选。",
            "4. 预算化大纲和扩场景候选通过审查和用户批准前，不得覆盖正式 `plot/outline.md` 或 `scenes/`。",
            "5. 场景生成必须读取预算标准，避免把长篇目标压缩成短篇摘要。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
