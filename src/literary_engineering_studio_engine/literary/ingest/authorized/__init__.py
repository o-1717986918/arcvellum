"""Contracts for authorized literary source distribution."""

from .contracts import (
    AUTHORIZED_WORK_SCHEMA,
    AuthorizationGrant,
    AuthorizedSourceFile,
    AuthorizedWorkManifest,
    DistributionScope,
    RightsBasis,
)
from .verification import (
    AuthorizedSourceVerification,
    verify_authorized_source_bundle,
)
from .reader import (
    AUTHORIZED_READER_SCHEMA,
    load_authorized_reader_units,
    read_authorized_reader_body,
    write_authorized_reader_manifest,
)

__all__ = [
    "AUTHORIZED_WORK_SCHEMA",
    "AUTHORIZED_READER_SCHEMA",
    "AuthorizationGrant",
    "AuthorizedSourceFile",
    "AuthorizedSourceVerification",
    "AuthorizedWorkManifest",
    "DistributionScope",
    "RightsBasis",
    "load_authorized_reader_units",
    "read_authorized_reader_body",
    "verify_authorized_source_bundle",
    "write_authorized_reader_manifest",
]
