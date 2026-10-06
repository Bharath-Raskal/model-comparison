"""Score every model in results/ against data/labels.jsonl and write results/REPORT.md.

run.py calls this after every run, so the report always compares all models run so far.
"""
import json
from datetime import datetime
from pathlib import Path

from request import load_categories, load_jsonl

ROOT = Path(__file__).parent
PRICE_NOTE = ("Prices come from models.json: Claude rows use Anthropic list prices (confirm against the "
              "Bedrock pricing page), Jev uses TypeSafe's published price, local models cost $0.")


def spend_line(results_dir):
    cap = json.loads((ROOT / "guardrails.json").read_text(encoding="utf-8"))["max_usd_per_run"]
    spend_file = results_dir / "spend.json"
    spent = json.loads(spend_file.read_text(encoding="utf-8"))["total_usd"] if spend_file.exists() else 0.0
    return f"Paid runs so far: ${spent:.4f} in total; each run is capped at ${cap:.2f} (guardrails.json)."


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))] if ordered else 0


def score_model(name, answers, truth, names, cfg):
    per_cat = {}
    for cat in names:
        in_cat = [a for a in answers if truth[a["id"]] == cat]
        per_cat[cat] = round(100 * sum(a["label"] == cat for a in in_cat) / len(in_cat)) if in_cat else None
    tokens_in = sum(a["input_tokens"] for a in answers)
    tokens_out = sum(a["output_tokens"] for a in answers)
    cost = tokens_in / 1e6 * cfg.get("usd_per_mtok_in", 0) + tokens_out / 1e6 * cfg.get("usd_per_mtok_out", 0)
    latencies = [a["latency_ms"] for a in answers]
    return {
        "model": name,
        "answered": len(answers),
        "accuracy": round(100 * sum(a["label"] == truth[a["id"]] for a in answers) / len(answers), 1),
        "not_a_category": sum(a["label"] not in names for a in answers),
        "per_category": per_cat,
        "avg_ms": round(sum(latencies) / len(latencies)),
        "p95_ms": percentile(latencies, 95),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost,
        "cost_per_1k_emails": cost / len(answers) * 1000,
        "settings": f"effort {cfg['effort']}" if cfg.get("effort") else "-",
        "answers": {a["id"]: a["label"] for a in answers},
    }


def write_report(rows, names, n_emails, path):
    def best(key, low=False):
        ranked = sorted(rows, key=lambda r: r[key], reverse=not low)
        return ranked[0]["model"] if ranked else "-"

    summary = (f"{len(rows)} models on {n_emails} CRM emails: most accurate {best('accuracy')}, "
               f"fastest {best('avg_ms', low=True)}, cheapest {best('cost_per_1k_emails', low=True)}.")
    lines = [
        "# Model comparison report", "", summary, "",
        f"Generated {datetime.now():%Y-%m-%d %H:%M}. Accuracy = answers matching data/labels.jsonl.", "",
        "## Overall", "",
        "| Model | Settings | Emails | Accuracy % | Avg ms | p95 ms | Tokens in | Tokens out | Run cost $ | $ per 1k emails |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['model']} | {r['settings']} | {r['answered']} | {r['accuracy']} | {r['avg_ms']} | {r['p95_ms']} | {r['tokens_in']:,} | "
                     f"{r['tokens_out']:,} | {r['cost_usd']:.4f} | {r['cost_per_1k_emails']:.4f} |")
    lines += ["", "## Accuracy by category (%)", "",
              "| Model | " + " | ".join(names) + " | Not a category |",
              "|---|" + "---|" * (len(names) + 1)]
    for r in rows:
        cats = " | ".join("-" if r["per_category"][c] is None else str(r["per_category"][c]) for c in names)
        lines.append(f"| {r['model']} | {cats} | {r['not_a_category']} |")
    lines += ["", "## Notes", "",
              f"- A model with fewer than {n_emails} emails was a --limit trial run; compare it with care.",
              "- \"Not a category\" counts refusals, truncations and errors; each is scored as a miss.",
              f"- {PRICE_NOTE}",
              f"- {spend_line(path.parent)}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)


def score(results_dir=ROOT / "results", quiet=False):
    truth = {r["id"]: r["label"] for r in load_jsonl("labels.jsonl")}
    names = [c["name"] for c in load_categories()]
    configs = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    rows = []
    for resp_file in sorted(results_dir.glob("*/responses.jsonl")):
        answers = [json.loads(l) for l in resp_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        if answers:
            name = resp_file.parent.name
            run_file = resp_file.parent / "run.json"  # the settings this run actually used
            cfg = json.loads(run_file.read_text(encoding="utf-8"))["config"] if run_file.exists() else configs.get(name, {})
            rows.append(score_model(name, answers, truth, names, cfg))
    rows.sort(key=lambda r: -r["accuracy"])
    report = write_report(rows, names, len(truth), results_dir / "REPORT.md")
    if not quiet:
        print(report)
    return rows


if __name__ == "__main__":
    score()
