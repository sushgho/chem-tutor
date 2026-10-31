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


if __name__ == "__main__":
    unittest.main()
