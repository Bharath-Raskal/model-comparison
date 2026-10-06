"""The one request every model gets: same instructions, same categories, same email text.

Wording comes from the prompt version folder, emails and the answer key from the input version folder.
"""
import json
from dataclasses import dataclass

from versions import data_dir, resolve

MAX_EMAIL_CHARS = 8000  # spend guard: refuse oversized emails instead of silently truncating
QUESTION = "Which category does this email to a CRM sales team belong in?"


@dataclass(frozen=True)
class Request:
    email_id: str
    system: str          # instructions + category list, identical for every email
    user: str            # the email itself
    categories: tuple    # category names, in file order
    question: str        # one-line question, for decision models that take a question + options
    criteria: dict       # category name -> description, for decision models' Choice options


def load_categories(prompt=None):
    return json.loads((data_dir("prompt", resolve(prompt=prompt)["prompt"]) / "categories.json").read_text(encoding="utf-8"))


def load_prompt(prompt=None):
    return (data_dir("prompt", resolve(prompt=prompt)["prompt"]) / "prompt.txt").read_text(encoding="utf-8").strip()


def load_jsonl(name, input=None):
    with open(data_dir("input", resolve(input=input)["input"]) / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_requests(prompt=None, input=None):
    categories = load_categories(prompt)
    names = tuple(c["name"] for c in categories)
    criteria = {c["name"]: c["description"] for c in categories}
    listing = "\n".join(f"- {c['name']}: {c['description']}" for c in categories)
    system = load_prompt(prompt).replace("{categories}", listing)
    requests = []
    for e in load_jsonl("emails.jsonl", input):
        user = f"From: {e['from']}\nSubject: {e['subject']}\n\n{e['body']}"
        if len(user) > MAX_EMAIL_CHARS:
            raise ValueError(f"{e['id']} is {len(user)} chars, over the {MAX_EMAIL_CHARS} cap")
        requests.append(Request(e["id"], system, user, names, QUESTION, criteria))
    return requests
