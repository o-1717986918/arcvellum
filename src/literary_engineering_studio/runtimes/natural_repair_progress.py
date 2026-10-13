"""Stop repeated field failures; preserve one concrete corrective-feedback checkpoint."""
import json
from .natural_field_repair import repair_field_values
from .source_repair_budget import SourceRepairBudget, text_digest
from .natural_transport_store import save_json

MAX_SOURCE_FIELD_REPAIRS = 4


def _signature(error):
    return json.dumps(repair_field_values(error.payload,error.fields),sort_keys=True,ensure_ascii=False)


class SourceRepairProgress:
    def __init__(self, root=None, operation="", source=""):
        self.signatures=set()
        self.corrected=set()
        self.feedback=None
        self.budget = SourceRepairBudget(root, operation, text_digest(source)) if root is not None else None
        self.path = self.budget.root / (self.budget.key + ".progress.json") if self.budget else None
        if self.path and self.path.is_file():
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            self.signatures = set(saved["signatures"])
            self.corrected = set(saved["corrected"])
            self.feedback = saved["feedback"]

    def register(self,error):
        signature=_signature(error)
        if signature in self.signatures and self.feedback is None:
            raise error
        if len(self.signatures) >= MAX_SOURCE_FIELD_REPAIRS:
            raise error
        if self.budget:
            try:
                self.budget.claim("source-author", signature)
            except ValueError:
                raise error
        self.signatures.add(signature)
        self._save()
        return signature

    def feedback_fields(self):
        return {'validation_feedback':self.feedback} if self.feedback else {}

    def advance(self,answer,error,reply,signature):
        combined=getattr(error,'source_text',None)
        if not combined:
            raise error
        if _signature(error)!=signature:
            self.feedback=None
            if self.budget:
                self.budget.alias(text_digest(combined))
            self._save()
            return combined
        if signature in self.corrected:
            raise error
        self.corrected.add(signature)
        self.feedback={'failed_reply':reply,'invalid_fields':repair_field_values(error.payload,error.fields),
            'error':str(error),'request':'上一份补交仍未通过。仅纠正指定字段。审读引句选择 context.prose_source 的现有段落引用；旧版字符串只复制 context.prose；取材依据复制 context.material_source_evidence 的实际 text。不要添加评价、解释或改写；其余字段不变。'}
        self._save()
        return answer

    def _save(self):
        if self.path:
            save_json(self.path, {"signatures":sorted(self.signatures), "corrected":sorted(self.corrected), "feedback":self.feedback})

    def completed(self, binding):
        path = self.budget.root / (binding + ".completed.json") if self.budget else None
        return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else None

    def complete(self, binding, source, payload):
        if self.budget:
            save_json(self.budget.root / (binding + ".completed.json"), {"source":source,"payload":payload})
