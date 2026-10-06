"""Run one model over the emails and save its answers to results/<model>/.

    python run.py claude-sonnet-5-5 --limit 5 --live   # 5-email trial
    python run.py claude-sonnet-5-5 --live             # all 100

Spend limits live in guardrails.json. A run stops as soon as it passes the per-run token or dollar
cap. Every paid run is recorded in results/spend.json.
"""
import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from models import PROVIDERS, Result, make_model
from request import build_requests
from score import score

ROOT = Path(__file__).parent
LIMITS = json.loads((ROOT / "guardrails.json").read_text(encoding="utf-8"))


def cost_usd(cfg, tokens_in, tokens_out):
    return tokens_in / 1e6 * cfg.get("usd_per_mtok_in", 0) + tokens_out / 1e6 * cfg.get("usd_per_mtok_out", 0)


def load_spend(results_dir):
    path = results_dir / "spend.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"total_usd": 0.0, "runs": []}


def run(name, limit=None, live=False, results_dir=ROOT / "results"):
    cfg = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))[name]
    if PROVIDERS[cfg["provider"]].live and not live:
        raise SystemExit(f"{name} calls a paid API. Re-run with --live once you have approved the spend.")
    spend = load_spend(results_dir)
    budget = LIMITS["max_usd_per_run"]
    model = make_model(cfg)

    requests = build_requests()[:limit]
    worst = cost_usd(cfg, len(requests) * 600, len(requests) * LIMITS["max_output_tokens_per_email"])
    print(f"{name}: {len(requests)} emails, worst case ${worst:.2f}, this run stops at ${budget:.2f}")

    out_dir = results_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    total_in = total_out = 0
    stopped = ""
    started = time.time()
    with open(out_dir / "responses.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for i, req in enumerate(requests, 1):
            t0 = time.time()
            try:
                result = model.classify(req)
            except Exception as exc:  # keep going; the failure is recorded and scored as a miss
                result = Result("error", stop=f"{type(exc).__name__}: {exc}"[:200])
            row = {"id": req.email_id, **asdict(result), "latency_ms": round((time.time() - t0) * 1000)}
            f.write(json.dumps(row) + "\n")
            total_in += result.input_tokens
            total_out += result.output_tokens
            print(f"[{i}/{len(requests)}] {req.email_id} -> {result.label}")
            if total_in + total_out >= LIMITS["max_tokens_per_run"]:
                stopped = f"token cap {LIMITS['max_tokens_per_run']:,}"
            elif cost_usd(cfg, total_in, total_out) >= budget:
                stopped = f"dollar cap ${budget:.2f}"
            if stopped:
                print(f"Stopped after {i} emails: hit the {stopped}")
                break

    usd = cost_usd(cfg, total_in, total_out)
    summary = {
        "model": name, "config": cfg, "emails": i, "input_tokens": total_in, "output_tokens": total_out,
        "cost_usd": round(usd, 6), "seconds": round(time.time() - started, 1), "stopped": stopped,
    }
    (out_dir / "run.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if usd > 0:
        spend["total_usd"] = round(spend["total_usd"] + usd, 6)
        spend["runs"].append({"model": name, "emails": i, "usd": round(usd, 6), "at": f"{datetime.now():%Y-%m-%d %H:%M}"})
        (results_dir / "spend.json").write_text(json.dumps(spend, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    score(results_dir)  # refresh results/REPORT.md with every model run so far
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("model", help="a key from models.json")
    p.add_argument("--limit", type=int, help="only the first N emails (try 5 before a full run)")
    p.add_argument("--live", action="store_true", help="allow calls that cost money")
    a = p.parse_args()
    run(a.model, a.limit, a.live)
