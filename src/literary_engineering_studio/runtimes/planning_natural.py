"""Archive creative planning prose before registered technical extraction."""
import json
from hashlib import sha256
from types import SimpleNamespace
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, resolve_prompt_layer
from .scene_natural_output import NaturalOutputProcessor
from .scene_natural_output import render_style, creator_style
from .scene_creator_briefing import scene_creator_style
from .planning_reading import normalize_planning_weights


def planning_run(root, gateway, prompt, *, layer_id, resolver=None, event_sink=None):
    template = resolver(layer_id, root) if resolver else resolve_prompt_layer(prompt_layer_spec(layer_id)).text
    system = render_style(template, creator_style({"style": scene_creator_style(root)}))
    envelope = json.dumps({"schema": "arcvellum/default-conversation/v1", "system_prompt": system,
                           "prompt": prompt}, ensure_ascii=False)
    directory = root / "workflow/studio/planning-inputs"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (sha256(envelope.encode()).hexdigest() + ".json")).write_text(envelope, encoding="utf-8")
    answer_path = directory / (sha256(envelope.encode()).hexdigest() + ".original.md")
    if answer_path.is_file():
        return SimpleNamespace(answer=answer_path.read_text(encoding="utf-8"), reused=True)
    response = gateway.run(root, envelope, role="worker", timeout=900, **({"event_sink": event_sink} if event_sink else {}))
    answer_path.write_text(response.answer, encoding="utf-8")
    return response


def planning_payload(root, gateway, answer, *, kind, context):
    # Legacy cached and structured deliveries remain readable.
    from .pi_scene_payload import _answer_payload
    directory = root / "workflow/studio/planning-originals" / sha256(answer.encode()).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "original.md").write_text(answer, encoding="utf-8")
    try:
        payload = _answer_payload(answer)
        payload = normalize_planning_weights(payload)
        if kind == "planning-future-chapter" and "chapter_id" in payload and "scenes" in payload:
            return {"chapter": payload}
        return payload
    except ValueError:
        pass
    system = resolve_prompt_layer(prompt_layer_spec("scene.v2.transport.extractor")).text
    def invoke(system, prompt):
        return gateway.run(root, json.dumps({"schema": "arcvellum/default-conversation/v1",
            "system_prompt": system, "prompt": prompt}, ensure_ascii=False), role="transport", timeout=900).answer
    return NaturalOutputProcessor(directory, system, invoke).process(answer, kind=kind, context=context)


class PlanningNaturalDelivery:
    def __init__(self, resolver=None, context_provider=None):
        self.resolver = resolver
        self.context_provider = context_provider

    def __call__(self, root, gateway, prompt, *, kind, layer_id, context=None, event_sink=None):
        context = context or {}
        if self.context_provider and not context.get("planning_scope_frozen"):
            prompt += "\n## 当前作品的创作人格、作者方向与人物声音\n" + json.dumps(self.context_provider(root), ensure_ascii=False)
            context = {**context, "planning_scope_frozen": True}
        if kind == "planning-future":
            from .future_planning_natural import future_planning_delivery
            return future_planning_delivery(self, root, gateway, prompt, context=context or {}, layer_id=layer_id, event_sink=event_sink)
        response = planning_run(root, gateway, prompt, layer_id=layer_id, resolver=self.resolver, event_sink=event_sink)
        return planning_payload(root, gateway, response.answer, kind=kind, context=context or {})
