"""Local comparison page: pick a model and settings, run it, and compare every run so far.

    uv run python ui.py        then open http://127.0.0.1:8765

Listens on this machine only. Pressing Run on a paid model is the same as `run.py --live`, and the
guardrails.json caps apply exactly as on the command line. One run at a time.
"""
import json
import os
import socket
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import env  # noqa: F401  loads .env before any AWS or API client starts
from models import PROVIDERS, StrandsDecider
from request import build_requests, load_categories, load_jsonl
from run import LIMITS, run
from score import score
from versions import KINDS, code_history, code_version, index, resolve

ROOT = Path(__file__).parent
PORT = int(os.environ.get("PORT", 8765))  # PORT=8766 to run a second copy beside the first
EFFORTS = ("low", "medium", "high")
status = {"running": False, "model": None, "lines": [], "stop_requested": False}
lock = threading.Lock()


def decider_up():
    """True when the local Decider server answers on its port."""
    host = urllib.parse.urlparse(StrandsDecider.url)
    try:
        with socket.create_connection((host.hostname, host.port), timeout=0.3):
            return True
    except OSError:
        return False


def not_ready(cfg):
    """Why a model can't run yet, or None."""
    if cfg["provider"] == "strands-decider" and not decider_up():
        return "start it first: uv run strands-decider serve <model> (see README)"
    if cfg["provider"] == "jev" and not os.environ.get("TYPESAFE_API_KEY"):
        return "add TYPESAFE_API_KEY to .env, then restart the page"
    return None


def state(versions):
    models = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    requests = build_requests(**versions)
    emails = {e["id"]: e for e in load_jsonl("emails.jsonl", versions["input"])}
    spend_file = ROOT / "results" / "spend.json"
    idx = index()
    return {
        "models": [{"name": n, "provider": c["provider"], "live": PROVIDERS[c["provider"]].live,
                    "effort": c.get("effort"), "usd_in": c.get("usd_per_mtok_in", 0),
                    "usd_out": c.get("usd_per_mtok_out", 0), "not_ready": not_ready(c)}
                   for n, c in models.items()],
        "efforts": EFFORTS,
        "categories": [c["name"] for c in load_categories(versions["prompt"])],
        "category_descriptions": load_categories(versions["prompt"]),
        "guardrails": LIMITS,
        "prompt": requests[0].system,
        "emails": [{"id": l["id"], "subject": emails[l["id"]]["subject"], "from": emails[l["id"]]["from"],
                    "body": emails[l["id"]]["body"], "expected": l["label"]}
                   for l in load_jsonl("labels.jsonl", versions["input"])],
        "rows": score(quiet=True, **versions),
        "spend": json.loads(spend_file.read_text(encoding="utf-8")) if spend_file.exists() else {"total_usd": 0, "runs": []},
        "status": status,
        "selected": versions,
        "versions": {k: {"current": idx[k]["current"], "history": idx[k]["history"]} for k in KINDS},
        "code": code_version(),
        "code_history": code_history(),
    }


def start_run(model, limit, effort, versions):
    def log(line):
        status["lines"].append(line)

    def work():
        try:
            run(model, limit=limit, live=True, overrides={"effort": effort} if effort else None, log=log,
                should_stop=lambda: status["stop_requested"], **versions)
        except SystemExit as stop:
            log(f"Stopped: {stop}")
        except Exception as exc:
            log(f"Failed: {type(exc).__name__}: {exc}")
        finally:
            status["running"] = False

    status.update(running=True, model=model, lines=[], stop_requested=False)
    threading.Thread(target=work, daemon=True).start()


def pick_versions(params):
    """Prompt/input versions from a query or body; falls back to the current ones."""
    return resolve(params.get("prompt") or None, params.get("input") or None)


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self.send(200, (ROOT / "ui.html").read_bytes(), "text/html; charset=utf-8")
        elif url.path == "/api/state":
            params = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            try:
                self.send(200, state(pick_versions(params)))
            except SystemExit as bad:
                self.send(400, {"error": str(bad)})
        elif url.path == "/api/progress":
            self.send(200, status)
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/stop":
            if not status["running"]:
                return self.send(409, {"error": "nothing is running"})
            status["stop_requested"] = True
            status["lines"].append("Stop requested: finishing the email in progress, then scoring what is done")
            return self.send(202, {"stopping": status["model"]})
        if self.path != "/api/run":
            return self.send(404, {"error": "not found"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        models = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
        model, limit, effort = body.get("model"), body.get("limit"), body.get("effort")
        if model not in models:
            return self.send(400, {"error": f"unknown model {model}"})
        if not_ready(models[model]):
            return self.send(400, {"error": f"{model}: {not_ready(models[model])}"})
        if effort and (effort not in EFFORTS or models[model]["provider"] != "bedrock"):
            return self.send(400, {"error": "effort applies to Claude models only: low, medium or high"})
        if limit is not None and (not isinstance(limit, int) or not 1 <= limit <= 100):
            return self.send(400, {"error": "emails must be 1 to 100"})
        try:
            versions = pick_versions(body)
        except SystemExit as bad:
            return self.send(400, {"error": str(bad)})
        with lock:
            if status["running"]:
                return self.send(409, {"error": f"{status['model']} is still running"})
            start_run(model, limit, effort, versions)
        self.send(202, {"started": model, **versions})

    def log_message(self, *args):  # keep the console for run progress only
        pass


if __name__ == "__main__":
    print(f"Open http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
