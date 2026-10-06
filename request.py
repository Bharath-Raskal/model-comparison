"""The one request every model gets: same instructions, same categories, same email text."""
import json
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent / "data"
MAX_EMAIL_CHARS = 8000  # spend guard: refuse oversized emails instead of silently truncating


@dataclass(frozen=True)
class Request:
    email_id: str
    system: str          # instructions + category list, identical for every email
    user: str            # the email itself
    categories: tuple    # category names, in file order
    question: str        # one-line question, for decision models that take a question + options


def load_categories():
    return json.loads((DATA / "categories.json").read_text(encoding="utf-8"))


def load_jsonl(name):
    with open(DATA / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_requests():
    categories = load_categories()
    names = tuple(c["name"] for c in categories)
    listing = "\n".join(f"- {c['name']}: {c['description']}" for c in categories)
    system = (DATA / "prompt.txt").read_text(encoding="utf-8").strip().replace("{categories}", listing)
    requests = []
    for e in load_jsonl("emails.jsonl"):
        user = f"From: {e['from']}\nSubject: {e['subject']}\n\n{e['body']}"
        if len(user) > MAX_EMAIL_CHARS:
            raise ValueError(f"{e['id']} is {len(user)} chars, over the {MAX_EMAIL_CHARS} cap")
        requests.append(Request(e["id"], system, user, names, "Which category fits this email best?"))
    return requests


def answer_schema(categories):
    """JSON schema that only allows one of the category names."""
    return {
        "type": "object",
        "properties": {"category": {"type": "string", "enum": list(categories)}},
        "required": ["category"],
        "additionalProperties": False,
    }
