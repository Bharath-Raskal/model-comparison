"""Score every model in one results folder against its input version's answer key and write REPORT.md.

run.py calls this after every run, so each prompt/input combination's report stays current.
"""
import json
from datetime import datetime
from pathlib import Path

from request import load_categories, load_jsonl
from versions import code_version, info, resolve, results_dir as version_results

ROOT = Path(__file__).parent
PRICE_NOTE = ("Prices come from models.json: Claude rows use Anthropic list prices (confirm against the "
              "Bedrock pricing page), Jev uses TypeSafe's published price, local models cost $0.")


def spend_line():
    cap = json.loads((ROOT / "guardrails.json").read_text(encoding="utf-8"))["max_usd_per_run"]
    spend_file = ROOT / "results" / "spend.json"
    spent = json.loads(spend_file.read_text(encoding="utf-8"))["total_usd"] if spend_file.exists() else 0.0
    return f"Paid runs so far: ${spent:.4f} in total; each run is capped at ${cap:.2f} (guardrails.json)."


def percentile(values, p):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1))))] if ordered else 0


def score_model(name, answers, truth, names, cfg, meta=None):
    meta = meta or {}
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
        "model_id": cfg.get("model_id", "-"),
        "run_at": meta.get("run_at", "-"),
        "answers": {a["id"]: a["label"] for a in answers},
    }


def write_report(rows, names, n_emails, path, prompt, input):
    def best(key, low=False):
        ranked = sorted(rows, key=lambda r: r[key], reverse=not low)
        return ranked[0]["model"] if ranked else "-"

    pv, iv = info("prompt", prompt), info("input", input)
    summary = (f"{len(rows)} models on {n_emails} CRM emails: most accurate {best('accuracy')}, "
               f"fastest {best('avg_ms', low=True)}, cheapest {best('cost_per_1k_emails', low=True)}.")
    lines = [
        f"# Model comparison report: prompt {prompt}, input {input}", "", summary, "",
        f"- Prompt {prompt} ({pv['since']}): {pv['note']}",
        f"- Input {input} ({iv['since']}): {iv['note']}",
        f"- Generated {datetime.now():%Y-%m-%d %H:%M} on code {code_version()['label']}.", "",
        "## Overall", "",
        "| Model | Settings | Emails | Accuracy % | Avg ms | p95 ms | Tokens in | Tokens out | Run cost $ | $ per 1k emails | Last run |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['model']} | {r['settings']} | {r['answered']} | {r['accuracy']} | {r['avg_ms']} | {r['p95_ms']} | "
                     f"{r['tokens_in']:,} | {r['tokens_out']:,} | {r['cost_usd']:.4f} | {r['cost_per_1k_emails']:.4f} | {r['run_at']} |")
    lines += ["", "## Accuracy by category (%)", "",
              "| Model | " + " | ".join(names) + " | Not a category |",
              "|---|" + "---|" * (len(names) + 1)]
    for r in rows:
        cats = " | ".join("-" if r["per_category"][c] is None else str(r["per_category"][c]) for c in names)
        lines.append(f"| {r['model']} | {cats} | {r['not_a_category']} |")
    lines += ["", "## Notes", "",
              f"- A model with fewer than {n_emails} emails was a trial or was stopped early; its scores cover only the emails it answered.",
              "- \"Not a category\" counts refusals, truncations and errors; each is scored as a miss.",
              f"- {PRICE_NOTE}",
              f"- {spend_line()}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(lines)


def score(prompt=None, input=None, results_dir=None, quiet=False):
    versions = resolve(prompt, input)
    results_dir = results_dir or version_results(**versions)
    truth = {r["id"]: r["label"] for r in load_jsonl("labels.jsonl", versions["input"])}
    names = [c["name"] for c in load_categories(versions["prompt"])]
    configs = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    rows = []
    for resp_file in sorted(results_dir.glob("*/responses.jsonl")):
        answers = [json.loads(l) for l in resp_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        if answers:
            name = resp_file.parent.name
            run_file = resp_file.parent / "run.json"  # the settings this run actually used
            meta = json.loads(run_file.read_text(encoding="utf-8")) if run_file.exists() else {}
            rows.append(score_model(name, answers, truth, names, meta.get("config", configs.get(name, {})), meta))
    rows.sort(key=lambda r: -r["accuracy"])
    results_dir.mkdir(parents=True, exist_ok=True)
    report = write_report(rows, names, len(truth), results_dir / "REPORT.md", **versions)
    if not quiet:
        print(report)
    return rows


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--prompt")
    p.add_argument("--input")
    a = p.parse_args()
    score(a.prompt, a.input)
