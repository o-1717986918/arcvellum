"""Creative-advisor domain package with the historical service surface.

The package itself preserves ``literary_engineering_studio.advisor`` imports,
while its sibling modules remain addressable for inbox, persona, and snapshot
compatibility paths.  Re-exporting every non-dunder service symbol keeps the
former module-level API, including explicit test-facing private helpers.
"""

from . import service as _service

for _name, _value in vars(_service).items():
    if not _name.startswith("__"):
        globals().setdefault(_name, _value)
