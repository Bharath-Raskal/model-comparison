# model-comparison

Compares models on one task: sorting 100 CRM emails into 5 categories. Every model gets the same request and the same scoring.

## What is here

- `data/emails.jsonl`: 100 sample emails (made up, no real people).
- `data/categories.json`: the 5 categories and what each means.
- `data/labels.jsonl`: the correct category per email. Models never see this file.
- `request.py`: builds the one request every model gets. `models.py` holds one small adapter per provider.
- `run.py` saves answers to `results/<model>/`, and `score.py` writes `results/scores.md`.

## Models

- `claude-opus-5-5`, `claude-sonnet-5-5`: Claude on Amazon Bedrock, using your AWS login.
- `strands-decider-2b`: open-source decision model that runs on this machine (`pip install strands-decider`).
- `jev`: TypeSafe's hosted decision model; needs `TYPESAFE_API_KEY`, adapter pending their API docs.
- `fake`: keyword rules, free, for testing the pipeline.

## Run

```
python -m unittest discover tests
python run.py fake
python run.py claude-sonnet-5-5 --limit 5 --live
python score.py
```

Paid models refuse to run without `--live`. Spend guards: 1,024 output tokens and 60 seconds per call, 300k tokens per run, emails over 8,000 characters rejected.
