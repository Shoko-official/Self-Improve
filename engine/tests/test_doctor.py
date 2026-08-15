import unittest

from frontier_engine.__main__ import doctor


class DoctorTests(unittest.TestCase):
    def test_doctor_reports_a_healthy_protocol(self) -> None:
        report = doctor()
        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["protocol_version"], 1)
        self.assertGreaterEqual(report["host"]["logical_cores"], 1)
