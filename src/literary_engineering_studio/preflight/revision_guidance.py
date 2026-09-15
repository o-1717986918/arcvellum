"""Focused repair guidance for exact-source scene revisions."""


def revision_manifest_repair(message: str, anti_evasion_rows_required: bool) -> str:
    if "source_excerpt is not present in the exact source body" in message and not anti_evasion_rows_required:
        return (
            "精确源正文的确定性检查未要求 anti_evasion_rows，当前引用也不在源正文中。"
            "删除这条无证据记录；若没有其他逐字可核验的真实风险，将 anti_evasion_rows 设为空列表，"
            "并填写非空 anti_evasion_not_applicable_reason。不得引用本轮中间稿充当源正文。"
        )
    if "source_excerpt is not present in the exact source body" in message:
        return "逐字复制精确 revision_source 中真正命中风险的最小完整句段；不得概述、改写或引用中间稿。"
    if "revised_excerpt is not present in the revised candidate body" in message:
        return "逐字复制当前修订正文中落实该动作的最小完整句段；不得概述或填写计划中的候选句。"
    return "按 revision prompt 的 exact-source 与 anti_evasion_rows 契约修正 manifest；不得伪造摘要或换皮修订。"


__all__ = ["revision_manifest_repair"]
