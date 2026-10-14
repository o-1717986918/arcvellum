"""Describe a reached formal-unit limit from persisted scene receipts."""

from pathlib import Path


def formal_unit_checkpoint(project: Path, limit: int) -> str:
    if not limit:
        return ""
    committed = len(tuple((project / "workflow" / "scene_commits").glob("*.json")))
    if committed < limit:
        return ""
    return f"已达到长期目标的正式单元检查点：{committed}/{limit}。"


__all__ = ["formal_unit_checkpoint"]
