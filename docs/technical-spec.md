# Technical specification

What each file does, what goes over the wire to each model, and how every number in the report is computed.

## Files

| File | Job |
|---|---|
| `data/emails.jsonl`, `data/categories.json`, `data/prompt.txt` | The input: 100 emails, 5 categories, the shared instructions |
| `data/labels.jsonl` | The answer key; read only by the scorer |
| `request.py`, `models.py` | Build the one request per email; one adapter per provider |
| `run.py`, `score.py` | Run one model and save answers; score all models into `results/REPORT.md` |
| `ui.py`, `ui.html` | The local page at http://127.0.0.1:8765: run, stop, compare |

## Request per model

Claude (Bedrock runtime, model `us.anthropic.claude-<name>`, effort set per run):

```
system:   data/prompt.txt with the 5 categories filled in
user:     From: <sender>  Subject: <subject>  <body>
reply:    one category name, e.g. billing
```

Jev (`https://api.typesafe.ai/v1/systemone`) and Decider (`http://127.0.0.1:8000/v1/systemone`), same body:

```
state:     From: <sender>  Subject: <subject>  <body>
question:  type choice, instructions "Which category does this email to a CRM sales team belong in?"
criteria:  the 5 category names, each with its description
reply:     choice, confidence, probabilities, token usage
```

## Saved answer (one line per email)

`results/<model>/responses.jsonl` holds the email id, label, confidence, input tokens, output tokens, stop reason and latency.
`results/<model>/run.json` holds the settings that run used, its totals and why it stopped, if it did.

## Report numbers

- Accuracy % = matching answers / emails answered × 100, overall and per category.
- Avg ms and p95 ms come from each email's measured latency.
- Run cost = tokens in × input price + tokens out × output price, with prices per million tokens in `models.json`.
- $ per 1k emails = run cost / emails answered × 1,000.

## Spend guards (`guardrails.json`)

- Paid models run only with `--live` or the page's Run button, after a confirm that shows the worst-case cost.
- At most 512 output tokens and 60 seconds per email; a run stops at 150,000 tokens or $5.
- Stop on the page ends the run after the email in progress; the answers so far are kept and scored.
- Every paid run's cost is appended to `results/spend.json`. Secrets live only in `.env`, which git ignores.

## Adding a model

Add an entry to `models.json`. If the provider is new, add one adapter class in `models.py` returning a `Result`.
