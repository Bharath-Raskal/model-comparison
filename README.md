# model-comparison

Compares four AI models on one task, sorting 100 CRM emails into 5 categories, on accuracy, speed and cost.

## In two minutes

- **What it does:** each model reads the same 100 sample emails and picks a category for each one.
  The categories are new lead, customer support, billing, partner or vendor, and not CRM.
- **The models:** Claude Opus 5.5 and Sonnet 5.5 on AWS Bedrock, TypeSafe's Jev, and Strands Decider.
  Decider runs on this laptop for free; the others are paid cloud APIs.
- **Same input for all:** every model gets the email, one question and the 5 category descriptions.
  No model gets examples or the answers; only the packaging differs per model.
- **How it is scored:** an answer key holds the right category for every email, and models never see it.
  Each answer is marked right or wrong, then the report adds up accuracy, time per email and cost.
- **How to use it:** open the local page, pick a model, press Run, and watch the comparison update.
  Stop ends a run early and still scores the emails already answered; Print report saves the whole page as a PDF.
- **Spend safety:** paid runs need a click-to-confirm, and every run stops at $5 or 150,000 tokens.
  Keys live in `.env`, which is never committed.

How it works, and why a model misses: [docs/technical-approach.md](docs/technical-approach.md).
Files, request formats and formulas: [docs/technical-spec.md](docs/technical-spec.md).

## Setup

1. Copy `.env.example` to `.env` and fill it in. Sign in to AWS with `aws sso login --profile <name>`.
2. For Strands Decider, install it once with `uv sync --extra decider`, then keep its server running in its own terminal.
   The first start downloads the model from Hugging Face:

```
uv run strands-decider serve StrandsAgents/strands-decider-2B-hobson-v21 --device cpu --port 8000
```

## Run

The page: `uv run python ui.py`, then open http://127.0.0.1:8765. Or from the command line:

```
python -m unittest discover tests
uv run python run.py claude-sonnet-5-5 --limit 5 --live
uv run python run.py claude-sonnet-5-5 --live
uv run python score.py
```

Answers land in `results/prompt-<v>/input-<v>/<model>/`, and every run refreshes that folder's `REPORT.md`.

## Versions

- Prompt versions (`versions/prompt/v1`, `v2`, ...) hold the instructions and category descriptions; input versions (`versions/input/v1`, ...) hold the emails and the answer key.
- `versions.json` names the current one of each and keeps a one-line note per version. The page has a dropdown for each; `run.py` takes `--prompt` and `--input`.
- To add one: copy the current folder to the next number, edit it, add its note, set it as current.
- The code version shown on the page is the latest git commit, plus a flag when uncommitted changes are running.
