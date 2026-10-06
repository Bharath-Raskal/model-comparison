"""Run one model over the emails and save its answers to results/prompt-<v>/input-<v>/<model>/.

    python run.py claude-sonnet-5-5 --limit 5 --live            # 5-email trial on the current versions
    python run.py claude-sonnet-5-5 --live --prompt v1          # all 100, older prompt wording

Spend limits live in guardrails.json. A run stops as soon as it passes the per-run token or dollar
cap. Every paid run is recorded in results/spend.json.
"""
import argparse
import json
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import env  # noqa: F401  loads .env before any AWS or API client starts
from models import PROVIDERS, Result, make_model
from request import build_requests
from score import score
from versions import code_version, resolve, results_dir as version_results

ROOT = Path(__file__).parent
LIMITS = json.loads((ROOT / "guardrails.json").read_text(encoding="utf-8"))
SPEND_FILE = ROOT / "results" / "spend.json"


def cost_usd(cfg, tokens_in, tokens_out):
    return tokens_in / 1e6 * cfg.get("usd_per_mtok_in", 0) + tokens_out / 1e6 * cfg.get("usd_per_mtok_out", 0)


def load_spend():
    return json.loads(SPEND_FILE.read_text(encoding="utf-8")) if SPEND_FILE.exists() else {"total_usd": 0.0, "runs": []}


def run(name, limit=None, live=False, prompt=None, input=None, overrides=None, log=print,
        should_stop=lambda: False, results_dir=None):
    """overrides: per-run settings such as {"effort": "medium"}, saved with the run. log: progress sink.
    should_stop: checked before each email; when it returns True the run ends there, and the emails
    answered so far are saved and scored as a partial run."""
    cfg = {**json.loads((ROOT / "models.json").read_text(encoding="utf-8"))[name], **(overrides or {})}
    if PROVIDERS[cfg["provider"]].live and not live:
        raise SystemExit(f"{name} calls a paid API. Re-run with --live once you have approved the spend.")
    versions = resolve(prompt, input)
    results_dir = results_dir or version_results(**versions)
    spend = load_spend()
    budget = LIMITS["max_usd_per_run"]
    model = make_model(cfg)

    requests = build_requests(**versions)[:limit]
    worst = cost_usd(cfg, len(requests) * 600, len(requests) * LIMITS["max_output_tokens_per_email"])
    log(f"{name} on prompt {versions['prompt']}, input {versions['input']}: {len(requests)} emails, "
        f"worst case ${worst:.2f}, this run stops at ${budget:.2f}")

    out_dir = results_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    total_in = total_out = 0
    stopped = ""
    i = answered = 0
    started = time.time()
    # Answers go to a new file first; the previous results stay in place until this run has real answers.
    new_file = out_dir / "responses.new.jsonl"
    with open(new_file, "w", encoding="utf-8", newline="\n") as f:
        for n, req in enumerate(requests, 1):
            if should_stop():
                stopped = "stopped by you"
                log(f"Stopped by you after {i} emails; scoring those only")
                break
            i = n
            t0 = time.time()
            try:
                result = model.classify(req)
            except Exception as exc:  # keep going; the failure is recorded and scored as a miss
                result = Result("error", stop=f"{type(exc).__name__}: {exc}"[:200])
            row = {"id": req.email_id, **asdict(result), "latency_ms": round((time.time() - t0) * 1000)}
            f.write(json.dumps(row) + "\n")
            f.flush()  # every answered email is on disk even if the run is cut short
            answered += result.label != "error"
            total_in += result.input_tokens
            total_out += result.output_tokens
            log(f"[{i}/{len(requests)}] {req.email_id} -> {result.label}")
            if total_in + total_out >= LIMITS["max_tokens_per_run"]:
                stopped = f"token cap {LIMITS['max_tokens_per_run']:,}"
            elif cost_usd(cfg, total_in, total_out) >= budget:
                stopped = f"dollar cap ${budget:.2f}"
            if stopped:
                log(f"Stopped after {i} emails: hit the {stopped}")
                break

    usd = cost_usd(cfg, total_in, total_out)
    summary = {
        "model": name, "config": cfg, "emails": i, "input_tokens": total_in, "output_tokens": total_out,
        "cost_usd": round(usd, 6), "seconds": round(time.time() - started, 1), "stopped": stopped,
        "run_at": f"{datetime.now():%Y-%m-%d %H:%M}", "prompt_version": versions["prompt"],
        "input_version": versions["input"], "code": code_version()["label"],
    }
    if answered:
        new_file.replace(out_dir / "responses.jsonl")
        (out_dir / "run.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    else:  # every email failed: keep the previous results, leave the failed run beside them to inspect
        new_file.replace(out_dir / "responses.failed.jsonl")
        (out_dir / "run.failed.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        log(f"Every email failed, so the previous {name} results were kept. See {name}/responses.failed.jsonl")
    if usd > 0:
        spend["total_usd"] = round(spend["total_usd"] + usd, 6)
        spend["runs"].append({"model": name, **versions, "emails": i, "usd": round(usd, 6),
                              "at": f"{datetime.now():%Y-%m-%d %H:%M}"})
        SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
        SPEND_FILE.write_text(json.dumps(spend, indent=2) + "\n", encoding="utf-8")
    log(f"Done: {i} emails, {total_in:,} tokens in, {total_out:,} out, ${usd:.4f}")
    score(results_dir=results_dir, **versions)  # refresh this combination's REPORT.md
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("model", help="a key from models.json")
    p.add_argument("--limit", type=int, help="only the first N emails (try 5 before a full run)")
    p.add_argument("--live", action="store_true", help="allow calls that cost money")
    p.add_argument("--prompt", help="prompt version (default: current in versions.json)")
    p.add_argument("--input", help="input version (default: current in versions.json)")
    a = p.parse_args()
    run(a.model, a.limit, a.live, a.prompt, a.input)
