import unittest

from frontier_engine.delegation import DelegationTask, build_delegation_plan


class DelegationTests(unittest.TestCase):
    def test_plan_is_bounded_and_evidence_bearing(self) -> None:
        plan = build_delegation_plan("project", (DelegationTask("research", "Find primary sources"), DelegationTask("reviewer", "Check evidence")))
        self.assertEqual(plan.evidence, ("research:literature and evidence analysis", "reviewer:claim and provenance review"))

    def test_unknown_or_side_effecting_tasks_are_blocked(self) -> None:
        with self.assertRaisesRegex(ValueError, "FR-DELEGATION-SPECIALIST"):
            build_delegation_plan("project", (DelegationTask("browser", "Browse"),))
        with self.assertRaisesRegex(PermissionError, "FR-DELEGATION-APPROVAL"):
            build_delegation_plan("project", (DelegationTask("engineering", "Change code", True),))

    def test_duplicate_specialists_are_rejected(self) -> None:
        task = DelegationTask("data", "Inspect table")
        with self.assertRaisesRegex(ValueError, "FR-DELEGATION-DUPLICATE"):
            build_delegation_plan("project", (task, task))
