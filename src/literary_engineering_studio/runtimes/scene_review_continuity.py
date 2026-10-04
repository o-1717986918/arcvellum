"""Pass accepted editorial judgments to the next natural scene review."""
from hashlib import sha256
import json
from pathlib import Path


def review_continuity(root: Path, prose: str) -> dict:
    current = sha256(prose.encode("utf-8")).hexdigest()[:16]
    reviews = [path for path in root.glob("review_result_v2_*.json")
               if path.name != f"review_result_v2_{current}.json"]
    previous = None
    if reviews:
        path = max(reviews, key=lambda item: (item.stat().st_mtime_ns, item.name))
        previous = {"source": path.name,
                    "prose_sha256_prefix": path.stem.removeprefix("review_result_v2_"),
                    "review": json.loads(path.read_text(encoding="utf-8"))}
    return {"completed_reviews": len(reviews),
            "completed_revisions": len(list(root.glob("revision_result_v2_*.json"))),
            "previous": previous}
