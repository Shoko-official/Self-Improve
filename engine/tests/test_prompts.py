import unittest

from frontier_engine.prompts import compile_prompt


class PromptCompilerTests(unittest.TestCase):
    def test_each_variant_respects_its_explicit_budget(self) -> None:
        for variant in ("compact", "standard", "extended"):
            pack = compile_prompt(variant, "Preserve raw inputs.", ("read_file", "run_kernel"))
            self.assertLessEqual(pack.estimated_tokens, pack.token_budget)
            self.assertIn("Granted tools: read_file, run_kernel.", pack.content)

    def test_variants_progressively_load_scientific_guidance(self) -> None:
        compact = compile_prompt("compact")
        extended = compile_prompt("extended")
        self.assertNotIn("execution log is authoritative", compact.content)
        self.assertIn("execution log is authoritative", extended.content)

    def test_over_budget_project_instructions_fail_explicitly(self) -> None:
        with self.assertRaises(ValueError):
            compile_prompt("compact", "x" * 1000)
