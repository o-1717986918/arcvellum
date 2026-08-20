"""Reviewed longform inventory parsing contracts."""

from __future__ import annotations

import re


def parse_scene_inventory(text: str) -> list[dict[str, object]]:
    scenes = _parse_table_inventory(text)
    if not scenes:
        scenes = _parse_card_inventory(text)
    if not scenes:
        raise ValueError(
            "scene inventory contains no machine-readable scene rows; use the required "
            "scene table or a heading-plus-field-card inventory"
        )
    ids = [str(scene["scene_id"]) for scene in scenes]
    if len(ids) != len(set(ids)):
        raise ValueError("scene inventory contains duplicate scene ids")
    errors = _participant_errors(scenes)
    if errors:
        raise ValueError("scene inventory participant contract: " + "; ".join(errors))
    return scenes


def parse_chapter_obligations(text: str) -> dict[str, dict[str, str]]:
    chapters: dict[str, dict[str, str]] = {}
    current = ""
    labels = {
        "读者进入问题": "reader_question",
        "承诺回报": "promised_reward",
        "暂扣信息": "withheld_information",
        "兑现/延迟": "payoff_or_delay",
        "反摘要要求": "anti_summary_requirement",
        "章末钩子": "chapter_ending_hook",
    }
    for raw in text.splitlines():
        line = raw.strip()
        match = re.match(r"^###\s+Ch\s*0*(\d+)", line, re.IGNORECASE)
        if match:
            current = f"chapter_{int(match.group(1)):04d}"
            chapters.setdefault(current, {})
            continue
        if not current or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] in labels:
            chapters[current][labels[cells[0]]] = cells[1]
    return chapters


def scene_inventory_contract_issues(text: str) -> list[str]:
    try:
        parse_scene_inventory(text)
    except ValueError as exc:
        return [str(exc)]
    return []


def _parse_table_inventory(text: str) -> list[dict[str, object]]:
    scenes: list[dict[str, object]] = []
    volume_id = "volume_01"
    chapter_id = "chapter_0001"
    chapter_title = ""
    for raw in text.splitlines():
        line = raw.strip()
        volume = re.match(r"^##\s+卷([一二三四五六七八九十0-9]+)", line)
        if volume:
            volume_id = f"volume_{number(volume.group(1)):02d}"
            continue
        chapter = re.match(
            r"^###\s+Ch\s*0*(\d+)\s*[—-]\s*(.*?)\s*(?:\||$)",
            line,
            re.IGNORECASE,
        )
        if chapter:
            chapter_id = f"chapter_{int(chapter.group(1)):04d}"
            chapter_title = chapter.group(2).strip()
            continue
        row = _table_scene_row(line, volume_id, chapter_id, chapter_title)
        if row:
            scenes.append(row)
    return scenes


def _table_scene_row(
    line: str,
    volume_id: str,
    chapter_id: str,
    chapter_title: str,
) -> dict[str, object] | None:
    if not re.match(r"^\|\s*(?:SC|scene[_-]?)\s*-?0*\d+\s*\|", line, re.IGNORECASE):
        return None
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    if len(cells) < 11:
        if len(cells) <= 3:
            return None
        raise ValueError(f"invalid scene inventory row: {line[:160]}")
    if "场景" in cells[1] and ("目标" in cells[2] or "target" in cells[2].lower()):
        return None
    if "name" in cells[1].lower() and "target" in cells[2].lower():
        return None
    if not re.search(r"\d", cells[2]):
        raise ValueError(f"invalid scene inventory target: {line[:160]}")
    target = number(cells[2])
    if target <= 0:
        raise ValueError(f"invalid scene inventory target: {line[:160]}")
    return {
        "scene_id": f"scene_{number(cells[0]):04d}",
        "source_scene_id": cells[0],
        "name": cells[1],
        "chapter_id": chapter_id,
        "chapter_title": chapter_title,
        "volume_id": volume_id,
        "target_chars": target,
        "function": cells[3],
        "participants": split_people(cells[4]),
        "conflict": cells[5],
        "information_release": cells[6],
        "consequence": cells[7],
        "setup_payoff_role": cells[8],
        "rhythm_role": cells[9],
        "obligation": cells[10],
    }


def _parse_card_inventory(text: str) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    context = {
        "chapter_id": "chapter_0001",
        "volume_id": "volume_01",
        "chapter_title": "",
    }
    active: dict[str, object] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        volume = re.match(
            r"^##\s+(?:卷|第\s*([一二三四五六七八九十0-9]+)\s*卷)", line
        )
        chapter = re.match(
            r"^###\s+(?:chapter[_-]?|Ch\s*)0*(\d+)\s*(?:[|—-]\s*(.*?))?$",
            line,
            re.IGNORECASE,
        )
        scene = re.match(
            r"^####\s+((?:s|sc|scene)[_-]?\d+(?:[_-]\d+)*)\s*[|—-]\s*(.+?)\s*$",
            line,
            re.IGNORECASE,
        )
        if volume:
            context["volume_id"] = f"volume_{number(volume.group(1) or line):02d}"
        elif chapter:
            _append_card(cards, active)
            active = None
            context["chapter_id"] = f"chapter_{int(chapter.group(1)):04d}"
            context["chapter_title"] = str(chapter.group(2) or "").strip()
        elif scene:
            _append_card(cards, active)
            active = {
                **context,
                "source_scene_id": scene.group(1),
                "name": scene.group(2).strip(),
                "fields": {},
            }
        else:
            _capture_card_field(active, line)
    _append_card(cards, active)
    for ordinal, card in enumerate(cards, 1):
        card["scene_id"] = f"scene_{ordinal:04d}"
    return cards


def _append_card(
    cards: list[dict[str, object]],
    active: dict[str, object] | None,
) -> None:
    if active is None:
        return
    fields = active.get("fields")
    if not isinstance(fields, dict):
        return
    target = number(
        str(fields.get("目标汉字字符") or fields.get("目标中文内容字符") or "0")
    )
    values = {
        "function": _field_text(fields, "功能"),
        "participants": _field_text(fields, "参与角色"),
        "conflict": _field_text(fields, "冲突"),
        "information_release": _field_text(fields, "信息释放"),
        "consequence": _field_text(fields, "行动后果"),
        "rhythm_role": _field_text(fields, "节奏角色"),
    }
    if target <= 0 or not all(values.values()):
        return
    cards.append(
        {
            **{key: value for key, value in active.items() if key != "fields"},
            "target_chars": target,
            "function": values["function"],
            "participants": split_people(values["participants"]),
            "conflict": values["conflict"],
            "information_release": values["information_release"],
            "consequence": values["consequence"],
            "setup_payoff_role": _field_text(fields, "设置伏笔")
            or _field_text(fields, "回收伏笔"),
            "rhythm_role": values["rhythm_role"],
            "obligation": _field_text(fields, "读者义务"),
        }
    )


def _capture_card_field(active: dict[str, object] | None, line: str) -> None:
    if active is None or not line.startswith("|"):
        return
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    if len(cells) != 2 or cells[0] in {"字段", "---", "---:"}:
        return
    label = re.sub(r"[*`_\s]", "", cells[0])
    value = cells[1].strip()
    fields = active.get("fields")
    if label and value and not set(label) <= {"-", ":"} and isinstance(fields, dict):
        fields[label] = value


def _participant_errors(scenes: list[dict[str, object]]) -> list[str]:
    errors: list[str] = []
    for scene in scenes:
        for raw in scene.get("participants") or []:
            identity = str(raw or "").strip()
            if re.search(r"[()（）\[\]【】]", identity):
                errors.append(
                    f"{scene.get('scene_id') or 'scene'} participant `{identity}` contains an explanatory "
                    "parenthetical; keep only the bare identity and move the note to "
                    "information_release or conflict"
                )
    return errors


def _field_text(fields: dict[str, str], label: str) -> str:
    value = str(fields.get(label) or "").strip()
    return value if value not in {"无", "-", "暂无"} else ""


def split_people(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[、,，/]+", value)
        if item.strip() and item.strip() not in {"无", "-"}
    ]


def number(value: str) -> int:
    digits = re.search(r"\d+", value)
    if digits:
        return int(digits.group())
    chinese = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    return chinese.get(value.strip(), 1)


__all__ = [
    "number",
    "parse_chapter_obligations",
    "parse_scene_inventory",
    "scene_inventory_contract_issues",
    "split_people",
]
