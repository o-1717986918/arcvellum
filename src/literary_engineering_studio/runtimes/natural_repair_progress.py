"""Stop repeated field failures; preserve one concrete corrective-feedback checkpoint."""
import json
from .natural_field_repair import repair_field_values

MAX_SOURCE_FIELD_REPAIRS = 4


def _signature(error):
    return json.dumps(repair_field_values(error.payload,error.fields),sort_keys=True,ensure_ascii=False)


class SourceRepairProgress:
    def __init__(self):
        self.signatures=set()
        self.corrected=set()
        self.feedback=None

    def register(self,error):
        signature=_signature(error)
        if signature in self.signatures and self.feedback is None:
            raise error
        if len(self.signatures) >= MAX_SOURCE_FIELD_REPAIRS:
            raise error
        self.signatures.add(signature)
        return signature

    def feedback_fields(self):
        return {'validation_feedback':self.feedback} if self.feedback else {}

    def advance(self,answer,error,reply,signature):
        combined=getattr(error,'source_text',None)
        if not combined:
            raise error
        if _signature(error)!=signature:
            self.feedback=None
            return combined
        if signature in self.corrected:
            raise error
        self.corrected.add(signature)
        self.feedback={'failed_reply':reply,'invalid_fields':repair_field_values(error.payload,error.fields),
            'error':str(error),'request':'上一份补交仍未通过。仅纠正指定字段。审读引句选择 context.prose_source 的现有段落引用；旧版字符串只复制 context.prose；取材依据复制 context.material_source_evidence 的实际 text。不要添加评价、解释或改写；其余字段不变。'}
        return answer
