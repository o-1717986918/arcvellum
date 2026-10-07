"""Persist real gateway invocations and distinct usage updates for isolated acceptance."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4
from hashlib import sha256


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
        if max(self.count,len(self.usage_ids)) >= self.max_calls or time.monotonic() - self.started >= self.max_minutes * 60:
            raise AcceptanceBudgetReached("验收批次已达到调用或时间上限，保存后续进度。")
        self.count += 1
        started, events = time.monotonic(), []
        sink = kwargs.get("event_sink")
        def observe(event, data):
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
            row.update(seconds=round(time.monotonic()-started, 3), usage_events=events)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def invocation_phase(args, kwargs, phase):
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
    groups, seen = {}, set()
    for row in rows:
        attempt=row.get('invocation_id') or sha256(json.dumps(row,sort_keys=True).encode('utf-8')).hexdigest()
        key = row["phase"] + ":" + row["role"]
        group = groups.setdefault(key, {"calls": 0, "seconds": 0, "tokens": 0, "cost_usd": 0.0, "missing_usage": 0,
            "token_details": {field: 0 for field in ("input", "output", "reasoning", "cache_read", "cache_write")}})
        group["calls"] += 1; group["seconds"] += row["seconds"]
        unique = []
        for item in row.get("usage_events", []):
            usage_id = item.get("usage_id")
            identity=(attempt,usage_id)
            if not usage_id or identity in seen:
                continue
            seen.add(identity); unique.append(item)
        if not row.get("usage_events") or not any(item.get("usage_id") for item in row["usage_events"]):
            group["missing_usage"] += 1
        for item in unique:
            group["tokens"] += item.get("usage", {}).get("total_tokens", 0) or 0
            for field in group["token_details"]:
                group["token_details"][field] += item.get("usage", {}).get(field, 0) or 0
            cost = item.get("cost_usd")
            if cost is None or cost == 0 and item.get("usage", {}).get("total_tokens", 0):
                group["missing_usage"] += 1
            else:
                group["cost_usd"] += cost
    return {"invocations": len(rows), "distinct_usage_updates": len(seen), "groups": groups,
        "reported_cost_usd": round(sum(x["cost_usd"] for x in groups.values()), 8),
        "cost_source": "Pi runtime model metadata estimate; provider billing unverified",
        "missing_usage": sum(x["missing_usage"] for x in groups.values())}
