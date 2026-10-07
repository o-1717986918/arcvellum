"""Index preserved real artifacts; inferred text matches are labelled as such."""
from difflib import SequenceMatcher
from hashlib import sha256
import json
from pathlib import Path
from literary_engineering_studio.runtimes.pi_worker_protocol import last_worker_result

from .creative_ledger import summarize_calls
from .creative_runner import write_json


def evidence_index(directory: Path):
    costs = {str(path.relative_to(directory)): summarize_calls(path)
             for path in sorted(directory.rglob("calls.jsonl"))}
    probe_path = directory / "probe/result.json"
    probe = json.loads(probe_path.read_text(encoding="utf-8")) if probe_path.is_file() else {}
    probe_events = [row['data'] for row in probe.get('usage_events', []) if row.get('event') == 'usage.updated']
    probe_cost = sum(row.get('cost_usd') or 0 for row in probe_events)
    scenes, case_failures = [], {}
    for path in sorted(directory.glob("*/*/acceptance.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        case_failures[data['case_id']+'/'+data['variant']] = failures(path.parent / 'data/pi-conversations')
        for scene in data["scenes"]:
            tx = path.parent / "data/scene-transactions" / scene.get("transaction_id", "__missing__")
            prose = Path(scene["prose_path"]).read_text(encoding="utf-8") if scene.get("prose_path") else ""
            memory = tx / "scene_creator_memory.json"
            decisions = json.loads(memory.read_text(encoding="utf-8")).get("material_decisions", []) if memory.is_file() else []
            scenes.append({"case": data["case_id"], "variant": data["variant"], **scene,
                "transaction_path": str(tx), "prompt_snapshots": snapshots(tx),
                "creator_decisions": decisions, "materials": materials(tx, prose),
                "worker_failures": failures(path.parent / "data/pi-conversations", tx.name),
                "archive_reads": archive_reads(tx)})
    result = {"schema": "arcvellum/creative-acceptance-index/v1", "scenes": scenes,
        "cost_ledgers": costs, "probe": probe, "case_failures": case_failures,
        "reported_cost_usd": round(sum(c["reported_cost_usd"] for c in costs.values()) + probe_cost, 8),
        "invocations": sum(c["invocations"] for c in costs.values()) + bool(probe),
        "reported_provider_usage_updates": sum(c['distinct_usage_updates'] for c in costs.values()) + len(probe_events),
        "missing_usage": sum(c["missing_usage"] for c in costs.values()),
        "cost_source": "Pi runtime model metadata estimate; provider billing unverified",
        "literary_judgment": "See judgments.md; sequence matches alone do not establish literary use."}
    write_json(directory / "evidence-index.json", result)
    return result


def snapshots(tx):
    rows = []
    for path in tx.glob("prompt_assembly_v*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append({"path": str(path), "sha256": sha256(path.read_bytes()).hexdigest(),
            "layers": {key: sha256(text.encode()).hexdigest() for key, text in data.get("texts", {}).items()}})
    return rows


def materials(tx, prose):
    rows = []
    for path in sorted((tx / "v2/calls").glob("*.json")):
        call = json.loads(path.read_text(encoding="utf-8"))
        candidates = []
        for candidate in call.get("candidates", []):
            match = SequenceMatcher(None, candidate["text"], prose, autojunk=False).find_longest_match()
            shared = candidate["text"][match.a:match.a+match.size]
            candidates.append({"candidate_id": candidate["candidate_id"], "text": candidate["text"],
                "shared_literal_fragment": shared if match.size >= 12 else "",
                "prose_offset": match.b if match.size >= 12 else None,
                "match_method": "longest literal sequence; editorial adoption requires reading"})
        rows.append({"path": str(path), "request": call["request"], "role": call["role"],
            "invoked": call.get("invoked", False), "attachments": call.get("attachment_manifest", []),
            "answer": call.get("answer", ""), "candidates": candidates})
    return rows


def failures(root, transaction_id=None):
    rows = []
    for path in root.glob("*/runs/*/runtime.output.log"):
        if transaction_id:
            prompt_path = path.parent / 'conversation.prompt.md'
            prompt = json.loads(prompt_path.read_text(encoding='utf-8'))
            if transaction_id not in prompt.get('material_root', ''):
                continue
        data = last_worker_result(path)
        if data.get("status") != "completed":
            rows.append({"path": str(path), "scope": 'transaction' if transaction_id else 'case-variant',
                "status": data.get("status"), "message": data.get("message"),
                "provider_error": data.get("providerError"), "failure_kind": data.get("failureKind", "unreported"),
                "retryable": data.get("providerFailureRetryable"), "partial_chars": len(data.get("answer", ""))})
    return rows


def archive_reads(tx):
    rows = []
    for path in (tx.parent.parent / 'pi-conversations/worker/runs').glob('*/conversation.prompt.md'):
        try:
            prompt = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            continue
        if tx.name not in prompt.get('material_root', ''):
            continue
        events = path.parent / 'runtime.events.jsonl'
        calls = [json.loads(line) for line in events.read_text(encoding='utf-8').splitlines()] if events.is_file() else []
        calls = [call for call in calls if call.get('event') == 'tool.completed' and call.get('tool') == 'work_archive']
        rows.append({'path': str(events), 'successful_workspace_calls': len(calls),
            'receipts': [call['archive_receipt'] for call in calls if call.get('archive_receipt')],
            'missing_read_receipts': sum(not call.get('archive_receipt') for call in calls),
            'limitation': 'Legacy tool-name-only events establish invocation, not entry-level reading.'})
    return rows
