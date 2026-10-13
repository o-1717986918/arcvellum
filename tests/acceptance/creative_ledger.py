"""Persist real gateway invocations and distinct usage updates for isolated acceptance."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4
from hashlib import sha256
from literary_engineering_studio.runtime.usage_accounting import summarize_usage_events, usage_identity


class AcceptanceBudgetReached(RuntimeError):
    pass


class AcceptanceGateway:
    def __init__(self, gateway, directory: Path, *, max_calls=80, max_minutes=45):
        self.gateway, self.directory = gateway, directory
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "calls.jsonl"
        self.batch_id = str(uuid4())
        self.started = time.monotonic()
        self.count, self.max_calls, self.max_minutes = 0, max_calls, max_minutes
        self.usage_ids = set()
        self.phase = "create"

    def run(self, *args, **kwargs):
        return self._invoke("run", args, kwargs)

    def run_actor_turn(self, *args, **kwargs):
        return self._invoke("run_actor_turn", args, kwargs)

    def run_role_turn(self, *args, **kwargs):
        return self._invoke("run_role_turn", args, kwargs)

    def _invoke(self, method, args, kwargs):
        calls_reached = self.max_calls is not None and max(self.count, len(self.usage_ids)) >= self.max_calls
        time_reached = self.max_minutes is not None and time.monotonic() - self.started >= self.max_minutes * 60
        if calls_reached or time_reached:
            raise AcceptanceBudgetReached("验收批次已达到调用或时间上限，保存后续进度。")
        self.count += 1
        started, events, runtime_events = time.monotonic(), [], []
        sink = kwargs.get("event_sink")
        def observe(event, data):
            if event in {'role.invocation.started','runner.provider.request.started',
                         'runner.http.attempt.started','runner.http.attempt.completed','runner.http.attempt.failed','usage.updated'}:
                runtime_events.append({'event':event,'data':data,'at':data.get('created_at','')})
            if event == "usage.updated":
                events.append(data)
                if data.get('usage_id'):
                    self.usage_ids.add(data['usage_id'])
            if sink:
                sink(event, data)
        kwargs = {**kwargs, "event_sink": observe}
        row = {"batch_id": self.batch_id, "invocation_id":str(uuid4()), "phase": invocation_phase(args, kwargs, self.phase),
            "method": method, "role": kwargs.get("role", "character-actor"),
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "failed"}
        try:
            result = getattr(self.gateway, method)(*args, **kwargs)
            row.update(status="completed", run_id=result.run_id, model=result.model)
            return result
        except Exception as error:
            row["error"] = str(error)[:1500]
            for field in ("failure_kind", "retryable", "run_root"):
                if hasattr(error, field):
                    row[field] = getattr(error, field)
            raise
        finally:
            purposes=[item['data']['call_purpose'] for item in runtime_events
                      if item['data'].get('call_purpose')]
            row.update(seconds=round(time.monotonic()-started, 3), usage_events=events,
                       runtime_events=runtime_events,call_purpose=next(iter(purposes),'unspecified'))
            if purposes:
                row['phase']=purposes[0]
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def invocation_phase(args, kwargs, phase):
    try:
        value=json.loads(args[1] if len(args)>1 else kwargs.get('prompt',''))
        if value.get('call_purpose'):
            return value['call_purpose']
    except (ValueError,TypeError,AttributeError):
        pass
    if "【十一种局部观察】" in str(kwargs.get('system_prompt') or ''):
        return "tone." + phase
    try:
        envelope = json.loads(args[1] if len(args) > 1 else kwargs.get("prompt", ""))
        prompt = envelope.get("prompt", "")
        if '"operation":' in prompt:
            task = json.loads(prompt)
            return "transport." + task.get("operation", "unknown")
        if "【十一种局部观察】" in envelope.get("system_prompt", ""):
            return "tone." + phase
    except (ValueError, TypeError, AttributeError):
        pass
    return phase


def summarize_calls(path: Path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []
    groups, seen, events = {}, set(), []
    for row in rows:
        key = row["phase"] + ":" + row["role"]
        group = groups.setdefault(key, {"calls":0,"seconds":0,"events":[],"unreported":0})
        group["calls"] += 1
        group["seconds"] += row["seconds"]
        group["unreported"] += int(not row.get("usage_events"))
        distinct = _distinct_accounting_events(_accounting_events([row]),seen)
        group["events"].extend(distinct);events.extend(distinct)
    for group in groups.values():
        accounting = summarize_usage_events(group.pop("events"))
        group.update(tokens=accounting["total_tokens"],cost_usd=accounting["catalog_estimate_usd"],
            missing_usage=accounting["unknown_catalog_cost_updates"]+group.pop("unreported"),
            token_details=accounting["token_details"],accounting=accounting)
    accounting=summarize_usage_events(events)
    return {"invocations":len(rows),"distinct_usage_updates":accounting["updates"],"groups":groups,
        "reported_cost_usd":round(accounting["catalog_estimate_usd"],8),
        "cost_source":"Pi runtime model metadata estimate; provider billing unverified",
        "missing_usage":sum(group["missing_usage"] for group in groups.values()),"accounting":accounting}


def _distinct_accounting_events(events,seen):
    result=[]
    call_fields={"role.invocation.started":"invocation_id","runner.provider.request.started":"model_request_id",
                 "runner.http.attempt.started":"http_attempt_id"}
    for event in events:
        name=event["event"];data=event["data"]
        if name=="usage.updated":
            identity=(name,usage_identity(data,event.get("event_id","")))
        elif name in call_fields:
            identity=(name,data.get(call_fields[name]))
        else:
            result.append(event);continue
        if identity in seen:
            continue
        seen.add(identity);result.append(event)
    return result


def _accounting_events(rows):
    events=[]
    for row in rows:
        identifier=row.get("invocation_id") or sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()
        if row.get("runtime_events"):
            events.extend({**event,"data":{"invocation_id":identifier,**event["data"]}} for event in row["runtime_events"])
            if not any(item["event"]=="role.invocation.started" for item in row["runtime_events"]):
                events.append({"event":"role.invocation.started","data":{"invocation_id":identifier}})
        else:
            events.append({"event":"role.invocation.started","data":{"invocation_id":identifier}})
            events.extend({"event":"usage.updated","at":row.get("created_at",""),
                "data":{"invocation_id":identifier,"model":row.get("model",""),**item},
                "event_id":identifier+":"+str(i)} for i,item in enumerate(row.get("usage_events",[])))
    return events
