"""Explicit execution purposes; never infer a business stage from prompt prose."""
from enum import Enum
import json


class CallPurpose(str, Enum):
    CREATOR = 'creator'
    REVISION = 'revision'
    MATERIAL = 'material'
    REVIEW = 'review'
    STYLE = 'style-choice'
    PERSONA = 'persona'
    SELECTION = 'selection'
    RECORD_REPAIR = 'record-repair'
    EVIDENCE_REPAIR = 'evidence-repair'
    LOCAL_EDIT = 'local-edit'
    PROJECT = 'project-control'
    UNSPECIFIED = 'unspecified'


def purpose_from_envelope(prompt, role):
    try:
        envelope = json.loads(prompt)
    except (ValueError, TypeError):
        envelope = {}
    value = envelope.get('call_purpose') if isinstance(envelope, dict) else None
    if value:
        return CallPurpose(value)
    if role == 'transport':
        return CallPurpose.RECORD_REPAIR
    if role == 'reviewer':
        return CallPurpose.REVIEW
    if role in {'character-actor','environment-writer','character-describer','event-narrator','scene-describer'}:
        return CallPurpose.MATERIAL
    return CallPurpose.UNSPECIFIED


def purpose_thinking(purpose, role, settings):
    if role == 'transport' or purpose in {CallPurpose.RECORD_REPAIR, CallPurpose.EVIDENCE_REPAIR}:
        return 'off'
    return str(settings.get('thinking') or 'low')


__all__ = ['CallPurpose', 'purpose_from_envelope', 'purpose_thinking']
