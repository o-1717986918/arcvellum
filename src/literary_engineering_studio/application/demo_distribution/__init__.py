"""Versioned demo bundle lifecycle for the Studio application."""

from .bundle import (
    DEMO_BUNDLE_SCHEMA,
    DemoBundleVerification,
    build_demo_bundle,
    verify_demo_bundle,
)
from .installer import (
    DemoInstallResult,
    clone_demo_project,
    install_demo_bundle,
)
from .completeness import DemoCompletenessReport, audit_demo_project

__all__ = [
    "DEMO_BUNDLE_SCHEMA",
    "DemoBundleVerification",
    "DemoCompletenessReport",
    "DemoInstallResult",
    "audit_demo_project",
    "build_demo_bundle",
    "clone_demo_project",
    "install_demo_bundle",
    "verify_demo_bundle",
]
