"""Two-scene batches through the production composition, with durable evidence."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from literary_engineering_studio.application.config import load_config
from literary_engineering_studio.application.container import build_application_container
from literary_engineering_studio.infrastructure.defaults import build_default_application_ports
from literary_engineering_studio.infrastructure.lean_scene_runtime import build_lean_scene_runtime
from literary_engineering_studio.persistence.scene_transactions import SceneTransactionRepository
from literary_engineering_studio.application.creator_persona import CreatorPersonaStore
from literary_engineering_studio.runtime.role_conversation import RoleConversationGateway
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec
from literary_engineering_studio_engine.public.literary import SceneExecutionMode

from .creative_cases import CASES, prepare_case
from literary_engineering_studio.application.style.initial_presets import initialize_style_presets
from literary_engineering_studio_engine.public.literary import ensure_default_style_mount
from .creative_ledger import AcceptanceGateway, summarize_calls
from .creative_lease import case_lease
from .creative_measurement import configure_targets

SCHEMA = "arcvellum/creative-acceptance/v1"
REPOSITORY = Path(__file__).resolve().parents[2]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=lambda item: item.value), encoding="utf-8")
    temporary.replace(path)


def configured_container(config_path, folder, *, tone=False):
    config = deepcopy(load_config(config_path))
    data = folder / "data"
    config["application"].update(data_root=str(data), database_path=str(data / "studio.sqlite3"),
        projects_root=str(folder / "projects"), scene_creator_v2={"enabled": True},
        less_ai_tone_experiment={"enabled": tone})
    return build_application_container(config, build_default_application_ports(config))


def ensure_persona(container, gateway, project, folder, case_id):
    store = CreatorPersonaStore(Path(container.config["application"]["data_root"]))
    if store.read_current(project)["active"]:
        return
    spec = prompt_layer_spec("project_agent.creator_persona.v2")
    source_key = sha256((spec.default_text + json.dumps(CASES[case_id], ensure_ascii=False, sort_keys=True)).encode()).hexdigest()
    source = folder.parent / ("persona-" + source_key + ".json")
    if source.is_file():
        text = json.loads(source.read_text(encoding="utf-8"))["text"]
    else:
        gateway.phase = "persona"
        answer = gateway.run(project, json.dumps({"schema": "arcvellum/default-conversation/v1",
            "call_purpose":"persona",
            "system_prompt": spec.default_text,
            "prompt": "本次交付一份小说家人格正文，直接供主创初始化加载。\n" + json.dumps(CASES[case_id], ensure_ascii=False)}, ensure_ascii=False),
            role="worker", timeout=180)
        text = answer.answer
        write_json(source, {"text": text, "run_id": answer.run_id, "model": answer.model,
                            "origin": "real model using top-level persona template",
                            "template_version": spec.package_version, "source_key": source_key})
    if len(text.strip()) > 4000:
        gateway.phase = "persona-revision"
        revised = gateway.run(project, json.dumps({"schema": "arcvellum/default-conversation/v1",
            "call_purpose":"persona",
            "system_prompt": prompt_layer_spec("project_agent.creator_persona.v2").default_text,
            "prompt": "把这份人格发展成直接加载的创作者指令，以鲜明的志趣与表达力量直陈。发展概述、省略、长时段、世界认识和情感伸展的讲述欲望。\n作品方向：" + json.dumps(CASES[case_id], ensure_ascii=False) + "\n原人格：\n" + text}, ensure_ascii=False), role="worker", timeout=180)
        write_json(source.with_name(source.stem + "-original-before-revision.json"), {"text": text})
        text = revised.answer
        write_json(source, {"text": text, "run_id": revised.run_id, "model": revised.model,
                            "origin": "real top-persona template revision",
                            "template_version": spec.package_version, "source_key": source_key})
    store.save(project, text, reason="隔离验收按同一作者方向初始化主创人格")


def configure_measurement(container, project, folder, profile_path=None):
    service = container.services.stylometry
    if service.workbench(project)["mount"]["enabled"] or not profile_path:
        return
    profile = service.import_parameters(project, profile_json=profile_path.read_text(encoding="utf-8"), title="来源画像")
    version = service.save_version(project, profile["profile_id"], json.dumps(profile["controls"]),
        title="隔离计量对照", intent=CASES[folder.parent.name]["style"])
    service.mount(project, version["version_id"], enabled=True, combine="append", usage="guide", expected_revision=0)


def run_batch(config_path, directory, case_id, *, variant="baseline", tone=False, profile_path=None,
              max_calls=80, max_minutes=45, max_revisions=3, measurement_config=None):
    with case_lease(directory / case_id / variant):
        return _run_batch(config_path,directory,case_id,variant=variant,tone=tone,profile_path=profile_path,
            max_calls=max_calls,max_minutes=max_minutes,max_revisions=max_revisions,
            measurement_config=measurement_config)


def _run_batch(config_path, directory, case_id, *, variant, tone, profile_path, max_calls,max_minutes,max_revisions,
               measurement_config=None):
    folder = directory / case_id / variant
    project = prepare_case(folder, case_id)
    container = configured_container(config_path, folder, tone=tone)
    data = Path(container.config["application"]["data_root"])
    gateway = AcceptanceGateway(RoleConversationGateway(container.config, data_root=data / "pi-conversations"),
        folder, max_calls=max_calls, max_minutes=max_minutes)
    report_path = folder / "acceptance.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {
        "schema": SCHEMA, "case_id": case_id, "variant": variant, "project_root": str(project),
        "data_root": str(data), "tone": tone, "measured": bool(profile_path), "scenes": []}
    report.setdefault("batches", []).append({"batch_id": gateway.batch_id,
        "source": source_version(), "max_calls": max_calls, "max_minutes": max_minutes,
        "literary_revision_limit": max_revisions, "technical_revision_limit": 6})
    try:
        report.pop('error',None)
        report['status'] = 'running'
        write_json(report_path, report)
        if CASES[case_id].get("literary_acceptance"):
            if not tone: raise ValueError("literary acceptance requires the optional tone editor enabled in this isolated instance")
            ensure_default_style_mount(project)
            catalog = initialize_style_presets(container.services.stylometry, project)
            if not catalog["enabled"] or any(not row["snapshot"]["enabled"] or row["snapshot"]["usage"] != "guide" for row in catalog["presets"]):
                raise ValueError("literary acceptance requires measured guidance on every eligible preset")
            report["measured"] = True; report["preset_catalog"] = catalog
            report['measurement_configuration'] = configure_targets(container.services.stylometry, project, folder, measurement_config)
            report['preset_catalog'] = container.services.stylometry.preset_catalog(project)
        else:
            configure_measurement(container, project, folder, profile_path)
        ensure_persona(container, gateway, project, folder, case_id)
        repository = SceneTransactionRepository(container.ports.persistence.unit_of_work)
        bundle = build_lean_scene_runtime(container.config, project_root=project, data_root=data, repository=repository)
        bundle.runtime._gateway = gateway
        for index in (1, 2):
            complete = run_scene(bundle, repository, gateway, project, folder, report,
                                 f"scene_{index:04d}", max_revisions)
            write_json(report_path, report)
            if not complete:
                break
        completed = len(report["scenes"]) == 2 and all(x["status"] == "committed" for x in report["scenes"])
        report["status"] = "completed" if completed else "blocked" if report["scenes"][-1].get("failure_reason") else "needs-analysis"
    except Exception as error:
        report.update(status="blocked", error=str(error)[:1500])
    finally:
        report["cost"] = summarize_calls(gateway.path)
        report["code_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True).strip()
        write_json(report_path, report)
        container.shutdown()
    return report


def run_scene(bundle, repository, gateway, project, folder, report, scene_id, max_revisions):
    tx = repository.latest_for_scene(str(project), scene_id)
    if tx is None:
        tx = bundle.service.prepare(project, scene_id, mode=SceneExecutionMode.STANDARD)
    row = next((row for row in report["scenes"] if row["scene_id"] == scene_id), None)
    if row is None:
        row = {"scene_id": scene_id, "transaction_id": tx.transaction_id, "steps": []}
        report["scenes"].append(row)
    for _ in range(24):
        state = repository.load(tx.transaction_id)
        row.update(status=state.status.value, revisions=state.revision_attempts, error=state.last_error)
        literary = literary_revisions(folder,scene_id,state.revision_attempts)
        row.update(literary_revisions=literary,technical_revisions=state.revision_attempts-literary)
        if state.status.value == "committed":
            return True
        if state.status.value == "revision-needed" and literary >= max_revisions:
            row["test_stop"] = "文学返修上限；正式状态保留"
            return False
        if state.status.value == "revision-needed" and state.revision_attempts-literary >= 6:
            row["test_stop"] = "技术校验重复失败上限；正式状态保留"
            return False
        gateway.phase = state.status.value
        step = bundle.coordinator.advance_transaction(tx.transaction_id, steward_approved=False)
        row["steps"].append(asdict(step))
        if step.blocked:
            row["failure_reason"] = step.message or "协调器保留了失败状态，请读取运行证据。"
        elif not step.waiting_human:
            row.pop('failure_reason', None)
        state = repository.load(tx.transaction_id)
        row.update(status=state.status.value, revisions=state.revision_attempts, error=state.last_error)
        row.pop('test_stop',None)
        record_scene(bundle, state, folder, row)
        write_json(folder / "acceptance.json", report)
        print(json.dumps({"case": report["case_id"], "variant": report["variant"], "scene": scene_id,
            "action": step.action, "status": state.status.value, "revisions": state.revision_attempts}, ensure_ascii=False), flush=True)
        if step.committed:
            return True
        if step.blocked or step.waiting_human:
            return False
    row["test_stop"] = "批次状态步数上限"
    return False


def record_scene(bundle, state, folder, row):
    path = folder / "evidence" / state.scene_id
    if state.creative_result:
        write_json(path / f"result-{state.revision_attempts}.json", state.creative_result.to_dict())
        (path / f"prose-{state.revision_attempts}.md").write_text(state.creative_result.prose, encoding="utf-8")
        row["prose_path"] = str(path / f"prose-{state.revision_attempts}.md")
        row["chars"] = len(state.creative_result.prose)
    if state.review:
        write_json(path / f"review-{state.revision_attempts}.json", asdict(state.review))
    if state.verification:
        write_json(path / f"verify-{state.revision_attempts}.json", state.verification.to_dict())


def literary_revisions(folder,scene_id,attempts):
    revisions = set()
    root = folder / 'evidence' / scene_id
    for path in root.glob('review-*.json'):
        index = int(path.stem.split('-')[-1])
        if index < attempts and json.loads(path.read_text(encoding='utf-8')).get('decision') == 'revise':
            revisions.add(index)
    for path in root.glob('verify-*.json'):
        index = int(path.stem.split('-')[-1])
        record = json.loads(path.read_text(encoding='utf-8'))
        if index < attempts and any(_literary_gate_issue(issue) for issue in record.get('issues') or []):
            revisions.add(index)
    return len(revisions)


def _literary_gate_issue(issue):
    code = str(issue.get('code') or '')
    return issue.get('severity') == 'hard' and (
        code.startswith('style-') or code in {'punctuation-dash-overuse', 'punctuation-staccato-period-overuse'})


def source_version():
    """Capture start-time provenance; each transaction also retains exact prompt texts."""
    from hashlib import sha256
    return {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY, text=True).strip(),
        "tracked_diff_sha256": sha256(subprocess.check_output(["git", "diff", "HEAD"], cwd=REPOSITORY)).hexdigest(),
        "working_tree_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=REPOSITORY, text=True).splitlines()}
