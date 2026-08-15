import unittest

from frontier_engine.credentials import CredentialHandle, inspect_credential, resolve_credential


class CredentialTests(unittest.TestCase):
    def test_status_is_redacted_and_resolution_is_explicit(self) -> None:
        handle = CredentialHandle("cloud.primary", "FRONTIER_TEST_TOKEN")
        status = inspect_credential(handle, {"FRONTIER_TEST_TOKEN": "secret-value"})
        self.assertEqual((status.name, status.available), ("cloud.primary", True))
        self.assertNotIn("secret-value", repr(status))
        self.assertEqual(resolve_credential(handle, {"FRONTIER_TEST_TOKEN": "secret-value"}), "secret-value")

    def test_missing_credentials_fail_at_execution_boundary(self) -> None:
        handle = CredentialHandle("cloud.primary", "FRONTIER_TEST_TOKEN")
        self.assertFalse(inspect_credential(handle, {}).available)
        with self.assertRaisesRegex(PermissionError, "FR-CREDENTIAL-MISSING"):
            resolve_credential(handle, {})

    def test_names_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "FR-CREDENTIAL-HANDLE"):
            CredentialHandle("bad handle", "FRONTIER_TOKEN")
        with self.assertRaisesRegex(ValueError, "FR-CREDENTIAL-ENV"):
            CredentialHandle("cloud", "frontier_token")
