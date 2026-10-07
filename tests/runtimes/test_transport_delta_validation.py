import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from literary_engineering_studio.runtimes.scene_creator_natural import _validate_transport_delta
from literary_engineering_studio.runtimes.scene_natural_output import NaturalOutputProcessor
from tests.runtimes.test_less_ai_tone_experiment import brief


class TransportDeltaValidationTests(unittest.TestCase):
    def test_same_body_is_reextracted_when_handoff_was_mistaken_for_target(self):
        source='陶婶把碗搁在台上，许钉蹲下去试桌腿。下一场接着修桌。'
        prompts=[]
        def extract(system,prompt):
            prompts.append(json.loads(prompt))
            payload={'prose':source,'decision_summary':'物件承担挽留','scene_delta':{}}
            if len(prompts)==1:
                payload['scene_delta']['continuity_changes']=[{'target_ref':'next_handoff','summary':'下一场接着修桌。','evidence':source}]
            else:
                payload['scene_delta']['next_handoff']=['下一场接着修桌。']
            return json.dumps(payload,ensure_ascii=False)
        with TemporaryDirectory() as tmp:
            output=NaturalOutputProcessor(Path(tmp),'整理',extract,validate_payload=lambda payload:_validate_transport_delta(payload,brief())).process(source,kind='creator',context={})
        self.assertEqual(output['prose'],source)
        self.assertEqual(len(prompts),2)
        self.assertIn('next_handoff',prompts[1]['transport_feedback']['issue'])
