# Model comparison report: prompt v1, input v1

4 models on 100 CRM emails: most accurate claude-opus-5-5, fastest jev, cheapest strands-decider-2b.

- Prompt v1 (2026-10-06 13:00): First wording of the instructions and category descriptions.
- Input v1 (2026-10-06 13:00): 100 made-up CRM emails with the answer key: 30 leads, 20 support, 15 billing, 15 vendor, 20 not CRM.
- Generated 2026-10-06 16:44 on code ff941af · 2026-10-06 15:09 · Enhance model comparison functionality: add timeout support for Strands Decider, improve error handling in run process, and implement a stop feature for ongoing runs. Update README for clarity and adjust category descriptions for better understanding. · plus uncommitted changes.

## Overall

| Model | Settings | Emails | Accuracy % | Avg ms | p95 ms | Tokens in | Tokens out | Run cost $ | $ per 1k emails | Last run |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | effort low | 100 | 100.0 | 2260 | 5682 | 41,910 | 600 | 0.1796 | 1.7964 | 2026-10-06 15:21 |
| claude-sonnet-5-5 | effort low | 100 | 99.0 | 871 | 969 | 34,710 | 687 | 0.0763 | 0.7629 | 2026-10-06 14:34 |
| jev | - | 100 | 98.0 | 362 | 427 | 51,173 | 5,937 | 0.0021 | 0.0215 | 2026-10-06 14:44 |
| strands-decider-2b | - | 100 | 90.0 | 9172 | 19064 | 24,139 | 100 | 0.0000 | 0.0000 | 2026-10-06 15:12 |

## Accuracy by category (%)

| Model | new_lead | customer_support | billing | partner_vendor | not_crm | Not a category |
|---|---|---|---|---|---|---|
| claude-opus-5-5 | 100 | 100 | 100 | 100 | 100 | 0 |
| claude-sonnet-5-5 | 100 | 100 | 93 | 100 | 100 | 1 |
| jev | 100 | 100 | 100 | 87 | 100 | 0 |
| strands-decider-2b | 83 | 95 | 100 | 80 | 95 | 0 |

## Notes

- A model with fewer than 100 emails was a trial or was stopped early; its scores cover only the emails it answered.
- "Not a category" counts refusals, truncations and errors; each is scored as a miss.
- Prices come from models.json: Claude rows use Anthropic list prices (confirm against the Bedrock pricing page), Jev uses TypeSafe's published price, local models cost $0.
- Paid runs so far: $0.7046 in total; each run is capped at $5.00 (guardrails.json).
