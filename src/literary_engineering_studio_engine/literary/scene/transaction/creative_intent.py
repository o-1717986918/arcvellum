"""Working literary intention for one scene, separate from committed story facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CreativeIntentV1:
    reader_experience: str
    reader_knows: str = ""
    reader_misreads: str = ""
    withheld: str = ""
    revision: int = 1

    SCHEMA = "arcvellum/creative-intent/v1"

    @classmethod
    def from_payload(
        cls, payload: Mapping[str, object], *, prior: CreativeIntentV1 | None = None,
    ) -> CreativeIntentV1:
        if not isinstance(payload, Mapping):
            raise ValueError("creative_intent must be an object")
        statement = _short_text(payload.get("reader_experience", prior.reader_experience if prior else None), required=True, limit=600)
        knows = _short_text(payload.get("reader_knows", prior.reader_knows if prior else ""), limit=400)
        misreads = _short_text(payload.get("reader_misreads", prior.reader_misreads if prior else ""), limit=400)
        withheld = _short_text(payload.get("withheld", prior.withheld if prior else ""), limit=400)
        if payload.get("schema") not in (None, cls.SCHEMA):
            raise ValueError("unsupported creative_intent schema")
        if prior is not None and not isinstance(prior, cls):
            raise ValueError("prior creative_intent has the wrong type")
        revision = prior.revision + 1 if prior else 1
        return cls(statement, knows, misreads, withheld, revision)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "schema": self.SCHEMA,
            "revision": self.revision,
            "reader_experience": self.reader_experience,
            "reader_knows": self.reader_knows,
            "reader_misreads": self.reader_misreads,
            "withheld": self.withheld,
        }


def _short_text(value: object, *, required: bool = False, limit: int = 400) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ValueError("creative_intent fields must be text")
    cleaned = " ".join(value.split())
    if required and not cleaned:
        raise ValueError("creative_intent needs a reader experience")
    if len(cleaned) > limit:
        raise ValueError("creative_intent field exceeds its limit")
    return cleaned
