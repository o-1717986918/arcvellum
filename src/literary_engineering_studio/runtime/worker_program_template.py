"""Registered fixed template for the legacy bounded Worker program."""

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec


WORKER_PROGRAM_TEMPLATE = prompt_layer_spec("formal.worker_program.v2.protocol").default_text + "\n"
