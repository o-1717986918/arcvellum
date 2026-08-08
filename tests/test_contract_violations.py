from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration.bundles import BundleViolation
from literary_engineering_studio.orchestration.campaign import CampaignViolation
from literary_engineering_studio.orchestration.chapter_facts import ChapterFactViolation
from literary_engineering_studio.orchestration.chapter_horizon import (
    ChapterHorizonViolation,
)
from literary_engineering_studio.orchestration.checkpoint import CheckpointViolation
from literary_engineering_studio.orchestration.literary_policy import (
    LiteraryPolicyViolation,
)
from literary_engineering_studio.orchestration.progress import (
    ProgressFingerprintViolation,
)
from literary_engineering_studio.orchestration.recovery import RecoveryViolation
from literary_engineering_studio.orchestration.replan import ReplanBudgetViolation
from literary_engineering_studio.orchestration.resource_gate import (
    ResourceGateViolation,
)
from literary_engineering_studio.orchestration.risk import SceneRiskViolation
from literary_engineering_studio.orchestration.rolling_horizon import (
    RollingHorizonViolation,
)
from literary_engineering_studio.orchestration.writer_policy import (
    WriterPolicyViolation,
)
from literary_engineering_studio.protocols.violations import (
    ContractViolation,
    RelatedContractViolation,
)
from literary_engineering_studio.runtime.context_cache import CacheKeyViolation
from literary_engineering_studio.runtime.output_repair import RepairViolation
from literary_engineering_studio.runtime.session_lease import SessionLeaseViolation


class ContractViolationTests(unittest.TestCase):
    def test_two_field_domain_names_are_compatibility_aliases(self):
        aliases = (
            BundleViolation,
            CampaignViolation,
            ChapterFactViolation,
            ChapterHorizonViolation,
            CheckpointViolation,
            ProgressFingerprintViolation,
            RecoveryViolation,
            ReplanBudgetViolation,
            ResourceGateViolation,
            SceneRiskViolation,
            RollingHorizonViolation,
            CacheKeyViolation,
            RepairViolation,
            SessionLeaseViolation,
        )

        self.assertTrue(all(alias is ContractViolation for alias in aliases))
        self.assertEqual(
            ContractViolation("missing", "missing evidence"),
            BundleViolation("missing", "missing evidence"),
        )

    def test_related_policy_violation_is_a_real_extension(self):
        self.assertIs(LiteraryPolicyViolation, RelatedContractViolation)
        self.assertIs(WriterPolicyViolation, RelatedContractViolation)
        violation = LiteraryPolicyViolation(
            code="prose-review",
            message="review required",
            related=("prose", "review"),
        )

        self.assertIsInstance(violation, ContractViolation)
        self.assertEqual(violation.related, ("prose", "review"))


if __name__ == "__main__":
    unittest.main()
