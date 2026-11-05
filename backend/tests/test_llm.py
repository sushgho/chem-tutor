import unittest
from unittest.mock import patch

from app import llm


class ModelConfigurationTests(unittest.TestCase):
    def test_retired_groq_model_uses_recommended_replacement(self):
        with patch.object(llm.settings, "model", "llama-3.3-70b-versatile"):
            self.assertEqual(llm.model_id(), "openai/gpt-oss-120b")

    def test_supported_custom_model_is_preserved(self):
        with patch.object(llm.settings, "model", "custom-model"):
            self.assertEqual(llm.model_id(), "custom-model")

    def test_fraction_simplifier_reduces_and_verifies_equivalent_fraction(self):
        result = llm.simplify_fraction(24, 132600)

        self.assertIn("GCD: 24", result)
        self.assertIn("simplified: 1/5525", result)
        self.assertIn("equivalence verified", result)

    def test_fraction_simplifier_normalizes_negative_denominator(self):
        result = llm.simplify_fraction(6, -8)

        self.assertIn("simplified: -3/4", result)
        self.assertIn("equivalence verified", result)

    def test_fraction_simplifier_rejects_zero_denominator(self):
        self.assertEqual(
            llm.simplify_fraction(5, 0),
            "error: denominator cannot be zero",
        )

    def test_fraction_simplifier_rejects_unreasonably_large_values(self):
        self.assertIn("too large", llm.simplify_fraction(10**101, 2))

    def test_fraction_simplifier_rejects_non_integer_values(self):
        self.assertIn("must be integers", llm.simplify_fraction(1.5, 2))

    def test_tool_schema_exposes_exact_fraction_simplifier(self):
        tool = next(
            item for item in llm.TOOLS
            if item["function"]["name"] == "fraction_simplifier"
        )

        self.assertEqual(
            tool["function"]["parameters"]["required"],
            ["numerator", "denominator"],
        )
        self.assertEqual(
            tool["function"]["parameters"]["properties"]["numerator"]["type"],
            "integer",
        )


if __name__ == "__main__":
    unittest.main()
