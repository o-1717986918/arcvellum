"""Whole-book literary choices followed by bounded chapter development."""
from .planning_reading import planning_reading
from .planning_checkpoint import future_checkpoint, load_checkpoint, save_checkpoint
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec


def future_planning_delivery(deliver, root, gateway, prompt, *, context, layer_id, event_sink=None):
    counts = context.get("chapter_counts") or {}
    layer_text = _planning_layer_text(deliver, root, layer_id)
    checkpoint = future_checkpoint(root, prompt, context, layer_id, layer_text)
    outline_prompt = prompt + "\n\n## 当前交付：全书未来纲要\n" + (
        "先交付全书叙事设计与各请求章节的文学任务、声音、时间组织、阅读经验、相对篇幅权重。"
        "为每章写明未来正文单元数量，以及单元名称与经验的简要目录。章节沿请求章序与章节编号组织。"
        "以自然排版的章节说明与单元目录，完整讲清这份纲要，供后续逐章展开。"
    )
    outline = load_checkpoint(checkpoint, 'outline') or deliver(root, gateway, outline_prompt, kind="planning-future-outline", layer_id=layer_id,
                      context=context, event_sink=event_sink)
    rows = outline.get("chapters")
    if not isinstance(rows, list) or [row.get("chapter_id") for row in rows] != list(counts):
        raise ValueError("future outline must retain requested chapter identities and order")
    save_checkpoint(checkpoint, 'outline', outline)
    chapters = []
    for row in rows:
        count = int(row["future_scene_count"])
        if not 0 <= count <= 20:
            raise ValueError("future outline unit count exceeds chapter capacity")
        task = prompt + "\n## 已选全书未来纲要\n" + planning_reading(outline)
        task += "\n## 当前交付：逐章展开\n" + (
            f"完整展开 {row['chapter_id']} 的 {count} 个未来正文单元。沿用已选全书旅程，"
            "为每个单元写出文学任务、叙述策略、时间、相对篇幅、参与人物及读者将经历的事。"
            "以自然排版的单元标题与段落说明逐一展开，章节间衔接参考全书纲要与先前已展开章节。"
        )
        task += "\n## 先前章节展开\n" + planning_reading(chapters)
        payload = load_checkpoint(checkpoint, row['chapter_id']) or deliver(root, gateway, task, kind="planning-future-chapter", layer_id=layer_id,
                          context={**context, "chapter_id": row["chapter_id"], "future_scene_count": count}, event_sink=event_sink)
        chapter = payload.get("chapter")
        if not isinstance(chapter, dict) or chapter.get("chapter_id") != row["chapter_id"] or len(chapter.get("scenes") or []) != count:
            raise ValueError("future chapter development must match its selected outline")
        save_checkpoint(checkpoint, row['chapter_id'], payload)
        chapters.append({**row, **chapter})
    return {"narrative_design": outline.get("narrative_design") or {}, "chapters": chapters}


def _planning_layer_text(deliver, root, layer_id):
    if getattr(deliver, 'resolver', None):
        return deliver.resolver(layer_id, root)
    return prompt_layer_spec(layer_id).default_text if root is not None else ''
