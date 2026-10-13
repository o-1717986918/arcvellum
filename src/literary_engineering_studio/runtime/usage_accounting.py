"""Pure deduplicated accounting; estimates and actual charges remain distinct."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import math

PRICE_SOURCE = 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
PRICE_OBSERVED_AT = '2026-10-11'
FLASH_IDS = {'deepseek-v4-flash', 'deepseek-flash'}
TOKEN_FIELDS = ('input', 'output', 'reasoning', 'cache_read', 'cache_write', 'total_tokens')
CALL_IDS = {'role.invocation.started':('invocation_ids','invocation_id'),
            'runner.provider.request.started':('model_request_ids','model_request_id'),
            'runner.http.attempt.started':('http_attempt_ids','http_attempt_id')}


def public_price_estimate(data, at):
    model = str(data.get('model') or '').rsplit('/',1)[-1]
    provider = str(data.get('provider') or str(data.get('model') or '').split('/')[0])
    usage = _usage(data)
    if model not in FLASH_IDS or provider != 'deepseek' or not _number(usage.get('total_tokens')):
        return None
    factor = _price_factor(at)
    if factor is None:
        return None
    amount = _price_amount(usage,factor)
    return {'amount':float(amount),'currency':'CNY','source':PRICE_SOURCE,
            'observed_at':PRICE_OBSERVED_AT,'kind':'public-price-estimate',
            'schedule_assumption':'Asia/Shanghai weekday schedule; holiday calendar unverified',
            'provider_billing_verified':False}


def _price_factor(at):
    try:
        time = datetime.fromisoformat(str(at).replace('Z','+00:00'))
        if time.tzinfo is None:
            return None
        local = time.astimezone(timezone(timedelta(hours=8)))
        peak = local.weekday() < 5 and (9 <= local.hour < 12 or 14 <= local.hour < 18)
        return Decimal(2 if peak else 1)
    except (ValueError,TypeError):
        return None


def _price_amount(usage,factor):
    # Output already includes reasoning; normalized input excludes cache hits.
    values = {key:Decimal(str(_number(usage.get(key)))) for key in TOKEN_FIELDS}
    return (values['input']+values['cache_write']+values['cache_read']*Decimal('.02')
            +values['output']*4)*factor/Decimal(1_000_000)


def usage_identity(data,fallback=''):
    identifier = str(data.get('usage_id') or '')
    if identifier.startswith('arcvellum-conversation-'):
        return identifier
    if identifier:
        return ':'.join((str(data.get('invocation_id') or data.get('session_id') or ''),identifier))
    return str(fallback)


def summarize_usage_events(events):
    ids = {key:set() for key in ('invocation_ids','model_request_ids','http_attempt_ids')}
    totals = {'token_details':{field:0 for field in TOKEN_FIELDS},'catalog':Decimal(0),'public':Decimal(0),
              'unknown_usage_updates':0,'unknown_catalog_cost_updates':0,'unknown_estimates':0,
              'sources':{},'usage_invocations':set(),'usage_ids':set(),'actual_records':{}}
    for event in events:
        name = str(event.get('event') or '')
        data = event.get('data') if isinstance(event.get('data'),dict) else event
        if name in CALL_IDS:
            field,key = CALL_IDS[name]
            if data.get(key):
                ids[field].add(data[key])
        if name == 'billing.actual_charge.recorded':
            _record_actual(totals,data)
        if name != 'usage.updated' and event.get('channel') != 'usage':
            continue
        identity = usage_identity(data,event.get('event_id') or event.get('sequence'))
        if not identity or identity in totals['usage_ids']:
            continue
        totals['usage_ids'].add(identity)
        _add_usage(totals,data,event.get('at') or data.get('created_at'))
    return _accounting_result(ids,totals)


def _add_usage(totals,data,at):
    if data.get('invocation_id'):
        totals['usage_invocations'].add(data['invocation_id'])
    usage = _usage(data)
    available = data.get('usage_available') is not False and _number(usage.get('total_tokens')) > 0
    totals['unknown_usage_updates'] += int(not available)
    for field in TOKEN_FIELDS:
        totals['token_details'][field] += int(_number(usage.get(field)))
    cost = _number(data.get('cost_usd'))
    if available and cost:
        totals['catalog'] += Decimal(str(cost))
    else:
        totals['unknown_catalog_cost_updates'] += 1
    price = data.get('price_estimate') or public_price_estimate(data,at)
    if available and _valid_price(price):
        totals['public'] += Decimal(str(price['amount']))
        totals['sources'][(price.get('source'),price.get('observed_at'))] = price
    else:
        totals['unknown_estimates'] += 1


def _accounting_result(ids,totals):
    updates = len(totals['usage_ids'])
    unknown_invocations = len(ids['invocation_ids']-totals['usage_invocations'])
    actual = list(totals['actual_records'].values())
    return {'total_tokens':totals['token_details']['total_tokens'],'cost_usd':float(totals['catalog']),
        'updates':updates,'token_details':totals['token_details'],'outer_invocations':len(ids['invocation_ids']),
        'recorded_model_turns':len(ids['model_request_ids']) or updates,
        'observed_http_attempts':len(ids['http_attempt_ids']) if ids['http_attempt_ids'] else None,
        'unknown_usage_updates':totals['unknown_usage_updates'],'unknown_usage_invocations':unknown_invocations,
        'usage_invocation_ids':sorted(totals['usage_invocations']),'unknown_public_price_updates':totals['unknown_estimates'],
        'unknown_catalog_cost_updates':totals['unknown_catalog_cost_updates'],
        'catalog_estimate_usd':float(totals['catalog']),
        'public_estimate_cny':float(totals['public']) if totals['sources'] else None,
        'public_estimate_complete':totals['unknown_estimates']==0 and updates>0 and unknown_invocations==0,
        'price_sources':list(totals['sources'].values()),'actual_charge':actual[0] if len(actual)==1 else None,
        'actual_charge_records':actual,'cost_source':'runtime-model-catalog-estimate; provider billing unverified',
        'usage_ids':sorted(totals['usage_ids']),**{key:sorted(value) for key,value in ids.items()}}


def _valid_price(price):
    return isinstance(price,dict) and price.get('currency')=='CNY' and _number(price.get('amount'))>0


def _record_actual(totals,data):
    if data.get('record_id') and data.get('currency') and data.get('source') and _number(data.get('amount'))>0:
        totals['actual_records'][data['record_id']] = {key:data.get(key) for key in
            ('record_id','amount','currency','source','observed_at','scope_id')}


def _usage(data):
    return data.get('usage') if isinstance(data.get('usage'),dict) else {}


def _number(value):
    try:
        number = float(value or 0)
        return max(0.0,number) if math.isfinite(number) else 0.0
    except (ValueError,TypeError):
        return 0.0


__all__ = ['public_price_estimate','usage_identity','summarize_usage_events']
