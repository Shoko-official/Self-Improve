import unittest

from frontier_engine.policy import DeviceRecord, OrganizationPolicy, PolicyError, evaluate_policy, validate_policy_layers


class PolicyTests(unittest.TestCase):
    def test_precedence_is_deterministic_and_exposes_evidence(self) -> None:
        decision = evaluate_policy("network.allow", {"default": {"network.allow": False}, "user": {"network.allow": True}, "organization": {"network.allow": False}})
        self.assertEqual((decision.value, decision.source), (False, "organization"))
        self.assertEqual(decision.evidence, ("organization:network.allow", "user:network.allow", "default:network.allow"))

    def test_missing_policy_is_explicit(self) -> None:
        decision = evaluate_policy("runtime.name", {"default": {}})
        self.assertEqual((decision.value, decision.source, decision.evidence), (None, "absent", ()))

    def test_policy_rejects_secret_keys_and_unknown_layers(self) -> None:
        with self.assertRaisesRegex(PolicyError, "FR-POLICY-SECRET"):
            validate_policy_layers({"organization": {"api_key": "never"}})
        with self.assertRaisesRegex(PolicyError, "FR-POLICY-LAYER"):
            validate_policy_layers({"remote": {"network.allow": True}})

    def test_records_are_typed(self) -> None:
        self.assertEqual(OrganizationPolicy("org", "Lab", {}).organization_id, "org")
        self.assertEqual(DeviceRecord("device", "Windows", "amd64").machine, "amd64")
