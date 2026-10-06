"""Checks the data and the full run -> score loop with the free fake model.

    python -m unittest discover tests
"""
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from request import build_requests, load_categories, load_jsonl  # noqa: E402
from run import run  # noqa: E402
from score import score  # noqa: E402


class DataTests(unittest.TestCase):
    def test_every_email_has_one_valid_label(self):
        emails = load_jsonl("emails.jsonl")
        labels = load_jsonl("labels.jsonl")
        names = {c["name"] for c in load_categories()}
        self.assertEqual(len(emails), 100)
        self.assertEqual([e["id"] for e in emails], [l["id"] for l in labels])
        self.assertTrue({l["label"] for l in labels} <= names)

    def test_category_mix(self):
        counts = Counter(l["label"] for l in load_jsonl("labels.jsonl"))
        self.assertEqual(counts, {"new_lead": 30, "customer_support": 20, "not_crm": 20,
                                  "billing": 15, "partner_vendor": 15})

    def test_emails_carry_no_answers(self):
        for e in load_jsonl("emails.jsonl"):
            self.assertEqual(set(e), {"id", "from", "subject", "body"})

    def test_every_model_gets_the_same_instructions(self):
        requests = build_requests()
        self.assertEqual(len({r.system for r in requests}), 1)


class PipelineTests(unittest.TestCase):
    def test_fake_run_then_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = run("fake", results_dir=Path(tmp))
            self.assertEqual(summary["emails"], 100)
            rows = score(results_dir=Path(tmp))
            self.assertEqual(rows[0]["model"], "fake")
            self.assertEqual(rows[0]["answered"], 100)
            self.assertTrue(0 < rows[0]["accuracy"] < 100)
            report = (Path(tmp) / "REPORT.md").read_text(encoding="utf-8")
            self.assertIn("1 models on 100 CRM emails: most accurate fake", report)
            self.assertIn("| fake | 100 |", report)

    def test_paid_models_need_live_flag(self):
        with self.assertRaises(SystemExit):
            run("claude-sonnet-5-5", limit=1)

if __name__ == "__main__":
    unittest.main()
