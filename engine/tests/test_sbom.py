import unittest
from pathlib import Path

from scripts.generate_sbom import create_sbom


class SbomTests(unittest.TestCase):
    def test_cyclonedx_inventory_is_unique_and_lock_backed(self) -> None:
        result = create_sbom(Path(__file__).parents[2])
        references = [component["bom-ref"] for component in result["components"]]
        self.assertEqual(result["bomFormat"], "CycloneDX")
        self.assertEqual(result["specVersion"], "1.6")
        self.assertEqual(len(references), len(set(references)))
        self.assertGreater(len(references), 100)
        self.assertIn("pkg:npm/react@18.3.1", references)
        self.assertIn("pkg:cargo/tauri@2.11.5", references)
        self.assertIn("pkg:pypi/pyinstaller@6.20.0", references)
        self.assertEqual(len(result["metadata"]["properties"]), 3)
