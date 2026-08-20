import unittest

from frontier_engine.system_prompt import PROMPT_VERSION, build_system_prompt


class SystemPromptTests(unittest.TestCase):
    def test_prompt_is_composed_from_host_context_and_declared_capabilities(self) -> None:
        prompt = build_system_prompt(
            "Cell atlas",
            "Keep raw counts immutable.",
            "ask",
            "extended",
            ["C:/research/atlas"],
            "science",
            ["generation.response", "skill.instructions:single-cell-qc"],
        )
        self.assertIn(PROMPT_VERSION, prompt)
        self.assertIn('<work_mode name="science">', prompt)
        self.assertIn("C:/research/atlas", prompt)
        self.assertIn("Keep raw counts immutable.", prompt)
        self.assertIn("skill.instructions:single-cell-qc", prompt)
        self.assertIn("A selected skill describes a method; it does not create a tool.", prompt)

    def test_prompt_does_not_invent_undeclared_tools(self) -> None:
        prompt = build_system_prompt("Local", "", "read", "compact", [])
        self.assertIn("- generation.response", prompt)
        self.assertNotIn("shell.execute", prompt)
        self.assertNotIn("connector.call", prompt)

    def test_prompt_rejects_invalid_modes(self) -> None:
        with self.assertRaisesRegex(ValueError, "work mode"):
            build_system_prompt("Local", "", "ask", "standard", [], "unsafe")

    def test_prompt_uses_ascii_punctuation(self) -> None:
        prompt = build_system_prompt("Local", "", "ask", "standard", [])
        self.assertNotIn("\u2014", prompt)
        self.assertNotIn("\u2013", prompt)
