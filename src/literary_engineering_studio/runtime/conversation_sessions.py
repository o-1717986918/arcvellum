"""Studio-owned opaque reference; SDK messages and storage paths remain private."""
from dataclasses import dataclass
from hashlib import sha256
import json


@dataclass(frozen=True)
class ConversationSessionRef:
    id: str
    binding: str

    @classmethod
    def bound(cls, scope, binding):
        digest = lambda value: sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        return cls(digest(scope), digest(binding))

    def to_dict(self):
        return {"schema":"arcvellum/conversation-session-ref/v1","id":self.id,"binding":self.binding}
