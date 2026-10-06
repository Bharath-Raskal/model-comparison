"""Local comparison page: pick a model and settings, run it, and compare every run so far.

    uv run python ui.py        then open http://127.0.0.1:8765

Listens on this machine only. Pressing Run on a paid model is the same as `run.py --live`, and the
guardrails.json caps apply exactly as on the command line. One run at a time.
"""
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import env  # noqa: F401  loads .env before any AWS or API client starts
from models import PROVIDERS, StrandsDecider
from request import build_requests, load_categories, load_jsonl
from run import LIMITS, run
from score import score

ROOT = Path(__file__).parent
PORT = 8765
EFFORTS = ("low", "medium", "high")
status = {"running": False, "model": None, "lines": [], "stop_requested": False}
lock = threading.Lock()


def decider_up():
    """True when the local Decider server answers on its port."""
    import urllib.parse
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


def state():
    models = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
    requests = build_requests()
    emails = {e["id"]: e for e in load_jsonl("emails.jsonl")}
    spend_file = ROOT / "results" / "spend.json"
    return {
        "models": [{"name": n, "provider": c["provider"], "live": PROVIDERS[c["provider"]].live,
                    "effort": c.get("effort"), "usd_in": c.get("usd_per_mtok_in", 0),
                    "usd_out": c.get("usd_per_mtok_out", 0), "not_ready": not_ready(c)}
                   for n, c in models.items()],
        "efforts": EFFORTS,
        "categories": [c["name"] for c in load_categories()],
        "guardrails": LIMITS,
        "prompt": requests[0].system,
        "emails": [{"id": i, "subject": emails[i]["subject"], "from": emails[i]["from"],
                    "body": emails[i]["body"], "expected": l["label"]} for i, l in
                   ((l["id"], l) for l in load_jsonl("labels.jsonl"))],
        "rows": score(ROOT / "results", quiet=True),
        "spend": json.loads(spend_file.read_text(encoding="utf-8")) if spend_file.exists() else {"total_usd": 0, "runs": []},
        "status": status,
    }


def start_run(model, limit, effort):
    def log(line):
        status["lines"].append(line)

    def work():
        try:
            run(model, limit=limit, live=True, overrides={"effort": effort} if effort else None, log=log,
                should_stop=lambda: status["stop_requested"])
        except SystemExit as stop:
            log(f"Stopped: {stop}")
        except Exception as exc:
            log(f"Failed: {type(exc).__name__}: {exc}")
        finally:
            status["running"] = False

    status.update(running=True, model=model, lines=[], stop_requested=False)
    threading.Thread(target=work, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send(200, (ROOT / "ui.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self.send(200, state())
        elif self.path == "/api/progress":
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
        with lock:
            if status["running"]:
                return self.send(409, {"error": f"{status['model']} is still running"})
            start_run(model, limit, effort)
        self.send(202, {"started": model})

    def log_message(self, *args):  # keep the console for run progress only
        pass


if __name__ == "__main__":
    print(f"Open http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
