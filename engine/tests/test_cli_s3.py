import os
import tempfile
import unittest
from unittest.mock import patch

from frontier_engine.cli import main


class CliS3Tests(unittest.TestCase):
    def test_cli_requires_named_environment_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            values = {"FRONTIER_DATA_DIR": directory}
            with patch.dict(os.environ, values, clear=True), patch("sys.argv", ["frontierctl", "s3-transfer", "--endpoint", "https://s3.example", "--s3-container", "bucket", "--prefix", "project/", "--object-key", "project/a", "--operation", "export"]):
                with self.assertRaises(SystemExit):
                    main()
