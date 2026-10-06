"""Score every model in results/ against data/labels.jsonl and write results/scores.md."""
import json
from collections import Counter
from pathlib import Path

from request import load_categories, load_jsonl

ROOT = Path(__file__).parent


def score(results_dir=ROOT / "results"):
    truth = {r["id"]: r["label"] for r in load_jsonl("labels.jsonl")}
    names = [c["name"] for c in load_categories()]
    rows = []
    for resp_file in sorted(results_dir.glob("*/responses.jsonl")):
        answers = [json.loads(l) for l in resp_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        correct = [a for a in answers if a["label"] == truth[a["id"]]]
        per_cat = {}
        for cat in names:
            in_cat = [a for a in answers if truth[a["id"]] == cat]
            per_cat[cat] = round(100 * sum(a["label"] == cat for a in in_cat) / len(in_cat)) if in_cat else None
        misses = Counter(a["label"] for a in answers if a["label"] not in names)
        rows.append({
            "model": resp_file.parent.name,
            "answered": len(answers),
            "accuracy": round(100 * len(correct) / len(answers), 1) if answers else 0.0,
            "per_category": per_cat,
            "not_a_category": dict(misses),
            "input_tokens": sum(a["input_tokens"] for a in answers),
            "output_tokens": sum(a["output_tokens"] for a in answers),
            "avg_latency_ms": round(sum(a["latency_ms"] for a in answers) / len(answers)) if answers else 0,
        })
    rows.sort(key=lambda r: -r["accuracy"])

    lines = [
        "# Model comparison: CRM email classification",
        "",
        f"{len(truth)} emails, {len(names)} categories. Accuracy = answers that match data/labels.jsonl.",
        "",
        "| Model | Emails | Accuracy % | " + " | ".join(names) + " | Tokens in | Tokens out | Avg ms |",
        "|---|---|---|" + "---|" * len(names) + "---|---|---|",
    ]
    for r in rows:
        cats = " | ".join("-" if r["per_category"][c] is None else str(r["per_category"][c]) for c in names)
        lines.append(f"| {r['model']} | {r['answered']} | {r['accuracy']} | {cats} | "
                     f"{r['input_tokens']:,} | {r['output_tokens']:,} | {r['avg_latency_ms']} |")
    (results_dir / "scores.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return rows


if __name__ == "__main__":
    score()
