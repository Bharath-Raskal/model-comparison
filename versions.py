"""Two independent version knobs, plus the code version from git.

- Prompt version: versions/prompt/<v>/ holds prompt.txt and categories.json (the wording models read).
- Input version:  versions/input/<v>/ holds emails.jsonl and labels.jsonl (the emails and the answer key).
- versions.json names the current one of each and keeps a one-line history.
- Results for one combination land in results/prompt-<v>/input-<v>/<model>/.
- Code version is whatever git says: last commit plus whether uncommitted changes are running.

To add a version: copy the current folder to the next number, edit it, add a history line, set "current".
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
INDEX = ROOT / "versions.json"
KINDS = ("prompt", "input")


def index():
    return json.loads(INDEX.read_text(encoding="utf-8"))


def current(kind):
    return index()[kind]["current"]


def known(kind):
    return [h["version"] for h in index()[kind]["history"]]


def info(kind, version):
    return next((h for h in index()[kind]["history"] if h["version"] == version),
                {"version": version, "note": "", "since": ""})


def resolve(prompt=None, input=None):
    """Fill in the current version for whichever knob was not given, and check both exist."""
    chosen = {"prompt": prompt or current("prompt"), "input": input or current("input")}
    for kind, v in chosen.items():
        if v not in known(kind):
            raise SystemExit(f"Unknown {kind} version {v}. Known: {', '.join(known(kind))}")
    return chosen


def data_dir(kind, version):
    return ROOT / "versions" / kind / version


def results_dir(prompt, input):
    return ROOT / "results" / f"prompt-{prompt}" / f"input-{input}"


def code_version():
    """Last commit (short hash, time, message) and whether uncommitted changes are running."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    line = git("log", "-1", "--format=%h%x09%ci%x09%s")
    if not line:
        return {"commit": "-", "at": "-", "message": "no git history", "dirty": False, "label": "no git history"}
    commit, at, message = line.split("\t", 2)
    dirty = bool(git("status", "--porcelain", "--untracked-files=no", "--", ".", ":!results"))
    at = at[:16]
    label = f"{commit} · {at} · {message}" + (" · plus uncommitted changes" if dirty else "")
    return {"commit": commit, "at": at, "message": message, "dirty": dirty, "label": label}


def code_history(limit=15):
    out = subprocess.run(["git", "log", f"-{limit}", "--format=%h%x09%ci%x09%s"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8").stdout.strip()
    return [dict(zip(("commit", "at", "message"), (c, a[:16], m)))
            for c, a, m in (l.split("\t", 2) for l in out.splitlines() if l)]
