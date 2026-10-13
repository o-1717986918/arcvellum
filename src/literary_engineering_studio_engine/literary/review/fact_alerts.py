"""Narrow arithmetic alerts, not a general semantic or literary verdict."""
from hashlib import sha256
import re

_YEARS = {'三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
_LAST_YEAR = re.compile(r'去年[^。！？\n“”「」『』"：:]{0,70}，(?:已经|已|到现在|至今)?(?P<years>[三四五六七八九十]|[3-9]|\d{2,})年(?:了|来)[^。！？\n“”「」『』"]*')
_FRAME = re.compile(r'(?:过了|过去了|又过|此后|之后|后来|多年后|数年后|次年|第二年|第三年|三年后|四年后)')


def current_fact_alerts(prose):
    """Flag adjacent relative date/duration claims in unquoted narration only.

    Separate sentences, explicit new temporal frames and speech are excluded.
    An alert requires independent review or escalation, never automatic rewriting.
    """
    alerts = []
    for match in _LAST_YEAR.finditer(prose):
        if _inside_quote(prose[:match.start()]) or _FRAME.search(match.group(0)):
            continue
        value = match['years']
        years = _YEARS.get(value) or int(value)
        alerts.append({'alert_id': sha256(match.group().encode()).hexdigest()[:20],
            'category': 'time', 'evidence': match.group(), 'elapsed_years': years,
            'reason': '相邻叙述把去年发生的变化与至少三年的持续时间并列；须核对是否同一事件。'})
    return alerts


def _inside_quote(prefix):
    return any(prefix.count(left) > prefix.count(right) for left, right in
               (('“', '”'), ('「', '」'), ('『', '』'))) or prefix.count('"') % 2 == 1
