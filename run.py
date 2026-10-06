"""Run one model over the emails and save its answers to results/<model>/.

    python run.py fake                       # free, no network
    python run.py claude-sonnet-5-5 --limit 5 --live
"""
import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from models import PROVIDERS, Result, make_model
from request import build_requests

ROOT = Path(__file__).parent
MAX_RUN_TOKENS = 300_000  # spend guard: stop the run once input + output tokens pass this


def run(name, limit=None, live=False, results_dir=ROOT / "results"):
    cfg = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))[name]
    if PROVIDERS[cfg["provider"]].live and not live:
        raise SystemExit(f"{name} calls a paid API. Re-run with --live once you have approved the spend.")
    model = make_model(cfg)

    requests = build_requests()[:limit]
    out_dir = results_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    total_in = total_out = 0
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
            if total_in + total_out > MAX_RUN_TOKENS:
                print(f"Stopped: run passed the {MAX_RUN_TOKENS:,} token cap")
                break

    summary = {
        "model": name, "config": cfg, "emails": i, "input_tokens": total_in,
        "output_tokens": total_out, "seconds": round(time.time() - started, 1),
    }
    (out_dir / "run.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("model", help="a key from models.json")
    p.add_argument("--limit", type=int, help="only the first N emails (try 5 before a full run)")
    p.add_argument("--live", action="store_true", help="allow calls that cost money")
    a = p.parse_args()
    run(a.model, a.limit, a.live)
