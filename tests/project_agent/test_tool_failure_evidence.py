"""A failed bridge action remains diagnosable without replacing it with success."""
from io import StringIO
from types import SimpleNamespace
import unittest
from literary_engineering_studio.project_agent.runtime import _handle_tool_call, _TurnState
from literary_engineering_studio.project_agent.contracts import BridgeEnvelope, BridgeMessageType


class ToolFailureEvidenceTests(unittest.TestCase):
    def test_error_and_request_identity_are_preserved_in_the_finished_event(self):
        events=[]
        call=BridgeEnvelope(type=BridgeMessageType.TOOL_CALL,message_id='m',turn_id='turn',
            payload={'request_id':'r','name':'project_planning_prepare','arguments':{}})
        def fail(_call):
            raise ValueError('first_window participants differ from authored scene')
        state=_TurnState()
        _handle_tool_call(SimpleNamespace(stdin=StringIO()),call,fail,{'project_planning_prepare'},state,
                          lambda event,data:events.append((event,data)))
        finished=events[-1][1]
        self.assertFalse(finished['ok'])
        self.assertEqual(finished['request_id'],'r')
        self.assertIn('participants differ',finished['error'])
        self.assertEqual(state.tool_calls,1)
