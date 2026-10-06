"""Checks the data for every prompt and input version, the reply parsing and the scoring, without calling any model.

    python -m unittest discover tests
"""
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import parse_label  # noqa: E402
from request import build_requests, load_categories, load_jsonl  # noqa: E402
from run import run  # noqa: E402
from score import score  # noqa: E402
from versions import current, data_dir, known  # noqa: E402

PROMPTS, INPUTS = known("prompt"), known("input")


class DataTests(unittest.TestCase):
    def test_every_version_folder_is_complete(self):
        for v in PROMPTS:
            for name in ("prompt.txt", "categories.json"):
                self.assertTrue((data_dir("prompt", v) / name).exists(), f"prompt/{v}/{name}")
        for v in INPUTS:
            for name in ("emails.jsonl", "labels.jsonl"):
                self.assertTrue((data_dir("input", v) / name).exists(), f"input/{v}/{name}")
        self.assertIn(current("prompt"), PROMPTS)
        self.assertIn(current("input"), INPUTS)

    def test_every_email_has_one_valid_label_in_every_combination(self):
        for p in PROMPTS:
            names = {c["name"] for c in load_categories(p)}
            for i in INPUTS:
                emails, labels = load_jsonl("emails.jsonl", i), load_jsonl("labels.jsonl", i)
                self.assertEqual(len(emails), 100, i)
                self.assertEqual([e["id"] for e in emails], [l["id"] for l in labels], i)
                self.assertTrue({l["label"] for l in labels} <= names, f"prompt {p} vs input {i}")

    def test_category_mix(self):
        counts = Counter(l["label"] for l in load_jsonl("labels.jsonl"))
        self.assertEqual(counts, {"new_lead": 30, "customer_support": 20, "not_crm": 20,
                                  "billing": 15, "partner_vendor": 15})

    def test_emails_carry_no_answers(self):
        for e in load_jsonl("emails.jsonl"):
            self.assertEqual(set(e), {"id", "from", "subject", "body"})

    def test_every_model_gets_the_same_instructions(self):
        for p in PROMPTS:
            self.assertEqual(len({r.system for r in build_requests(prompt=p)}), 1, p)

    def test_prompt_versions_differ(self):
        self.assertGreater(len({build_requests(prompt=p)[0].system for p in PROMPTS}), 1 if len(PROMPTS) > 1 else 0)


class PipelineTests(unittest.TestCase):
    def test_score_marks_saved_answers_against_the_key(self):
        truth = {l["id"]: l["label"] for l in load_jsonl("labels.jsonl")}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "claude-sonnet-5-5"
            out.mkdir()
            lines = []
            for i, (eid, label) in enumerate(truth.items()):  # first 75 right, last 25 wrong
                answer = label if i < 75 else "not_a_real_category"
                lines.append(json.dumps({"id": eid, "label": answer, "confidence": None, "input_tokens": 300,
                                         "output_tokens": 5, "stop": "end_turn", "latency_ms": 800}))
            (out / "responses.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            rows = score(results_dir=Path(tmp), quiet=True)
            self.assertEqual(rows[0]["accuracy"], 75.0)
            self.assertEqual(rows[0]["not_a_category"], 25)
            self.assertAlmostEqual(rows[0]["cost_usd"], 30000 / 1e6 * 2.0 + 500 / 1e6 * 10.0)
            report = (Path(tmp) / "REPORT.md").read_text(encoding="utf-8")
            self.assertIn(f"prompt {current('prompt')}, input {current('input')}", report)
            self.assertIn("| claude-sonnet-5-5 | effort low | 100 | 75.0 |", report)

    def test_reply_parsing(self):
        cats = ("billing", "not_crm")
        self.assertEqual(parse_label(" Billing.\n", cats), "billing")
        self.assertTrue(parse_label("I think billing", cats).startswith("invalid"))

    def test_paid_models_need_live_flag(self):
        with self.assertRaises(SystemExit):
            run("claude-sonnet-5-5", limit=1)

    def test_unknown_version_is_refused(self):
        with self.assertRaises(SystemExit):
            build_requests(prompt="v99")


if __name__ == "__main__":
    unittest.main()
