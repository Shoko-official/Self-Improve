import unittest
from unittest.mock import patch

from frontier_engine.kernels import PythonKernel, probe_r


class KernelTests(unittest.TestCase):
    def test_python_namespace_persists_and_restart_clears_it(self) -> None:
        kernel = PythonKernel()
        try:
            self.assertEqual(kernel.execute("sample_size = 41").state, "succeeded")
            self.assertEqual(kernel.execute("print(sample_size + 1)").stdout, "42\n")
            kernel.restart()
            self.assertEqual(kernel.execute("print('sample_size' in globals())").stdout, "False\n")
        finally:
            kernel.close()

    def test_python_failure_is_returned_not_swallowed(self) -> None:
        kernel = PythonKernel()
        try:
            result = kernel.execute("raise ValueError('bad input')")
            self.assertEqual(result.state, "failed")
            self.assertIn("ValueError", result.error or "")
        finally:
            kernel.close()

    def test_r_probe_reports_missing_runtime(self) -> None:
        with patch("frontier_engine.kernels.shutil.which", return_value=None):
            self.assertEqual(probe_r()["reason"], "FR-KERNEL-R-NOT-FOUND")
