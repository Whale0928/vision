from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PromptContractTest(unittest.TestCase):
    def test_prompt_requires_label_name_extraction_and_reasoning(self):
        prompt = (ROOT / "ai" / "prompt.txt").read_text(encoding="utf-8")

        self.assertIn("라벨에서 읽힌 이름 후보", prompt)
        self.assertIn("브랜드·증류소·제품명·연산·캐스크", prompt)
        self.assertIn("eng_name은 라벨에서 읽힌 이름 후보를 바탕으로", prompt)
        self.assertIn("identification_reason은 3~5문장", prompt)
        self.assertIn("단순히 \"라벨 텍스트로 식별했다\"처럼 쓰지 않는다", prompt)

    def test_schema_describes_rich_identification_fields(self):
        schema = json.loads((ROOT / "ai" / "response_schema.json").read_text(encoding="utf-8"))
        properties = schema["properties"]

        self.assertIn("라벨에서 읽힌 이름 후보", properties["eng_name"]["description"])
        self.assertIn("브랜드·증류소·제품명", properties["identification"]["description"])
        self.assertIn("3~5문장", properties["identification_reason"]["description"])
        self.assertIn("불확실성", properties["identification_reason"]["description"])


if __name__ == "__main__":
    unittest.main()
