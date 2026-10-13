"""Lossless context projections. Source storage and unequal versions remain intact."""
from copy import deepcopy
import json


def deduplicate_cards(context):
    result = deepcopy(context)
    frozen = {json.dumps(row["card"], ensure_ascii=False, sort_keys=True): row["digest"]
              for row in result.get("frozen_scene_cards", []) if row.get("digest")}
    for row in result.get("work_cards", []):
        card = row.get("card")
        key = json.dumps(card, ensure_ascii=False, sort_keys=True)
        if key in frozen:
            row.pop("card")
            row["target"] = card["target"]
            row["card_ref"] = {"digest": frozen[key], "delivered_via": "actor_card_context.frozen_scene_cards"}
    return result
