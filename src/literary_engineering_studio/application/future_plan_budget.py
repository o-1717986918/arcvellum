"""Allocate an unwritten literary suffix while preserving its committed prefix."""
from copy import deepcopy
import math


def proposed_counts(budget, committed, response):
    chapter_ids = [row["chapter_id"] for row in budget["chapter_budgets"]]
    current = committed[-1]["chapter_id"] if committed else chapter_ids[0]
    active = chapter_ids[chapter_ids.index(current):]
    rows = response.get("chapters") or []
    if [row.get("chapter_id") for row in rows if isinstance(row, dict)] != active:
        raise ValueError("future proposal must cover every remaining chapter in order")
    return {row["chapter_id"]: len(row.get("scenes") or []) +
            sum(scene["chapter_id"] == row["chapter_id"] for scene in committed) for row in rows}


def allocate_future_targets(budget, committed, response, counts):
    """Chapter weights apply to future capacity; existing scene targets stay fixed."""
    revised = deepcopy(budget)
    proposals = {row["chapter_id"]: row for row in response.get("chapters") or []}
    active, fixed, remaining, capacity = _remaining_capacity(revised, committed, counts)
    selected = [row for row in active if remaining[row["chapter_id"]]]
    minimums = [remaining[row["chapter_id"]] * 1800 for row in selected]
    if capacity < sum(minimums) or not selected:
        raise ValueError("future chapter counts exceed the remaining book capacity")
    weights = [_weight(proposals[row["chapter_id"]].get("length_weight", max(row["target_words"] - fixed[row["chapter_id"]], 1))) for row in selected]
    allocations = _bounded_distribution(capacity, weights, minimums)
    targets = {row["chapter_id"]: target for row, target in zip(selected, allocations)}
    for row in active:
        row["target_words"] = fixed[row["chapter_id"]] + targets.get(row["chapter_id"], 0)
    _volume_totals(revised)
    return revised


def _remaining_capacity(budget, committed, counts):
    active = [row for row in budget["chapter_budgets"] if row["chapter_id"] in counts]
    fixed = {row["chapter_id"]: 0 for row in active}
    remaining = dict(counts)
    for scene in committed:
        if scene["chapter_id"] in fixed:
            fixed[scene["chapter_id"]] += int(scene.get("target_chars") or 0)
            remaining[scene["chapter_id"]] -= 1
    finished_target = sum(int(row["target_words"]) for row in budget["chapter_budgets"] if row not in active)
    capacity = int(budget["totals"]["target_words"]) - finished_target - sum(fixed.values())
    return active, fixed, remaining, capacity


def _volume_totals(budget):
    for volume in budget["volume_budgets"]:
        members = [row for row in budget["chapter_budgets"] if row["volume_id"] == volume["volume_id"]]
        volume["target_words"] = sum(row["target_words"] for row in members)
        volume["avg_chapter_words"] = round(volume["target_words"] / len(members))


def _weight(value):
    weight = float(value)
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError("chapter length weights must be positive finite numbers")
    return weight


def _distribute(total, weights):
    exact = [total * value / sum(weights) for value in weights]
    values = [math.floor(value) for value in exact]
    for index in sorted(range(len(weights)), key=lambda index: exact[index] - values[index], reverse=True)[:total - sum(values)]:
        values[index] += 1
    return values


def _bounded_distribution(total, weights, minimums):
    active = list(range(len(weights)))
    result = [0] * len(weights)
    while active:
        proposed = _distribute(total, [weights[index] for index in active])
        below = [index for index, value in zip(active, proposed) if value < minimums[index]]
        if not below:
            for index, value in zip(active, proposed):
                result[index] = value
            break
        for index in below:
            result[index] = minimums[index]
            total -= minimums[index]
            active.remove(index)
    return result
