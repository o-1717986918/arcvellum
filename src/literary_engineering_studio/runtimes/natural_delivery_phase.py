"""Project an explicit author's phase without losing either prose or commissions."""
import re
from .natural_local_delivery import explicit_creator_phase
from .natural_transport_repair import NaturalSourceClarificationError


def project_creator_phase(answer, payload):
    phase = explicit_creator_phase(answer)
    declared = payload.get('delivery_phase')
    if declared is not None:
        pattern = r'"(?:delivery_phase|path)"\s*:\s*"(?:/delivery_phase|' + re.escape(str(declared)) + r')"'
        value = r'"value"\s*:\s*"' + re.escape(str(declared)) + r'"'
        if declared not in {'prepare', 'complete'} or not re.search(pattern, answer):
            raise NaturalSourceClarificationError('delivery_phase must be the original author\'s explicit prepare/complete choice', fields=['/delivery_phase'], payload=payload)
        if '"/delivery_phase"' in answer and not re.search(value, answer):
            raise NaturalSourceClarificationError('source phase value is missing', fields=['/delivery_phase'], payload=payload)
        phase = declared
    if phase == 'prepare' and payload.get('prose'):
        payload['pending_body_source'] = payload['prose']
        payload['prose'] = ''
    elif phase == 'complete' and payload.get('material_requests'):
        payload['completed_commission_notes'] = payload['material_requests']
        payload['material_requests'] = []
    if payload.get('prose') and payload.get('material_requests'):
        raise NaturalSourceClarificationError('creator transport mixes completed prose and pending material requests; select the source delivery phase', fields=['/delivery_phase'], payload=payload)
    return payload
