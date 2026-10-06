# model-comparison

Compares models on one task: sorting 100 CRM emails into 5 categories. Every model gets the same request and the same scoring.

## What is here

- `data/emails.jsonl`: 100 sample emails (made up, no real people).
- `data/categories.json`: the 5 categories and what each means.
- `data/labels.jsonl`: the correct category per email. Models never see this file.
- `data/prompt.txt`: the instructions every model gets; `{categories}` is filled from `categories.json`.
- `request.py` builds the one request per email, and `models.py` holds one small adapter per provider.
- `run.py` saves answers to `results/<model>/`, then refreshes `results/REPORT.md`: accuracy, speed and cost for every model run so far.

## Models

- `claude-opus-5-5`, `claude-sonnet-5-5`: Claude on Amazon Bedrock, using your AWS login.
- `strands-decider-2b`: open-source decision model that runs on this machine, free per call. It speaks the same API as Jev.
- `jev`: TypeSafe's hosted decision model; needs `TYPESAFE_API_KEY` in `.env`.

## Setup

Copy `.env.example` to `.env` and fill it in (it is git-ignored). Sign in to AWS with `aws sso login --profile <name>`.

For Strands Decider, install it once with `uv sync --extra decider`, then keep its local server running in its own terminal
(the first start downloads the model from Hugging Face):

```
uv run strands-decider serve StrandsAgents/strands-decider-2B-hobson-v19 --device cpu --port 8000
```

## Run

The page: `uv run python ui.py`, then open http://127.0.0.1:8765. Or from the command line:

```
python -m unittest discover tests
uv run python run.py claude-sonnet-5-5 --limit 5 --live
uv run python run.py claude-sonnet-5-5 --live
uv run python score.py
```

## Spend limits (`guardrails.json`)

- Paid models refuse to run without `--live`.
- Each email gets at most 512 output tokens and 60 seconds.
- A run stops at 150,000 tokens or $5.00, whichever comes first.
- Every paid run's cost is recorded in `results/spend.json` and shown in the report.
- Emails over 8,000 characters are rejected, not cut.
