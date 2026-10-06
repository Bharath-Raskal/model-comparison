# Model comparison report

3 models on 100 CRM emails: most accurate claude-opus-5-5, fastest jev, cheapest jev.

Generated 2026-10-06 14:57. Accuracy = answers matching data/labels.jsonl.

## Overall

| Model | Settings | Emails | Accuracy % | Avg ms | p95 ms | Tokens in | Tokens out | Run cost $ | $ per 1k emails |
|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | effort low | 100 | 100.0 | 2184 | 4733 | 34,710 | 795 | 0.1547 | 1.5474 |
| claude-sonnet-5-5 | effort low | 100 | 99.0 | 871 | 969 | 34,710 | 687 | 0.0763 | 0.7629 |
| jev | - | 100 | 98.0 | 362 | 427 | 51,173 | 5,937 | 0.0021 | 0.0215 |

## Accuracy by category (%)

| Model | new_lead | customer_support | billing | partner_vendor | not_crm | Not a category |
|---|---|---|---|---|---|---|
| claude-opus-5-5 | 100 | 100 | 100 | 100 | 100 | 0 |
| claude-sonnet-5-5 | 100 | 100 | 93 | 100 | 100 | 1 |
| jev | 100 | 100 | 100 | 87 | 100 | 0 |

## Notes

- A model with fewer than 100 emails was a trial or was stopped early; its scores cover only the emails it answered.
- "Not a category" counts refusals, truncations and errors; each is scored as a miss.
- Prices come from models.json: Claude rows use Anthropic list prices (confirm against the Bedrock pricing page), Jev uses TypeSafe's published price, local models cost $0.
- Paid runs so far: $0.2446 in total; each run is capped at $5.00 (guardrails.json).
