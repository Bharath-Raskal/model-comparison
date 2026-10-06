# Model comparison report: prompt v2, input v1

4 models on 100 CRM emails: most accurate claude-opus-5-5, fastest jev, cheapest strands-decider-2b.

- Prompt v2 (2026-10-06 15:03): Lead = wants to buy from us, vendor = wants to sell to us (promos and quotes included); not_crm is the explicit catch-all; never reply with a question.
- Input v1 (2026-10-06 13:00): 100 made-up CRM emails with the answer key: 30 leads, 20 support, 15 billing, 15 vendor, 20 not CRM.
- Generated 2026-10-06 16:45 on code ff941af · 2026-10-06 15:09 · Enhance model comparison functionality: add timeout support for Strands Decider, improve error handling in run process, and implement a stop feature for ongoing runs. Update README for clarity and adjust category descriptions for better understanding. · plus uncommitted changes.

## Overall

| Model | Settings | Emails | Accuracy % | Avg ms | p95 ms | Tokens in | Tokens out | Run cost $ | $ per 1k emails | Last run |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | effort low | 100 | 100.0 | 2251 | 4906 | 41,910 | 630 | 0.1802 | 1.8024 | 2026-10-06 16:22 |
| jev | - | 100 | 100.0 | 375 | 449 | 54,073 | 5,935 | 0.0023 | 0.0227 | 2026-10-06 16:18 |
| claude-sonnet-5-5 | effort low | 100 | 99.0 | 891 | 1092 | 41,910 | 714 | 0.0910 | 0.9096 | 2026-10-06 16:25 |
| strands-decider-2b | - | 100 | 87.0 | 9435 | 15294 | 27,039 | 100 | 0.0000 | 0.0000 | 2026-10-06 16:44 |

## Accuracy by category (%)

| Model | new_lead | customer_support | billing | partner_vendor | not_crm | Not a category |
|---|---|---|---|---|---|---|
| claude-opus-5-5 | 100 | 100 | 100 | 100 | 100 | 0 |
| jev | 100 | 100 | 100 | 100 | 100 | 0 |
| claude-sonnet-5-5 | 100 | 100 | 93 | 100 | 100 | 1 |
| strands-decider-2b | 77 | 95 | 100 | 80 | 90 | 0 |

## Notes

- A model with fewer than 100 emails was a trial or was stopped early; its scores cover only the emails it answered.
- "Not a category" counts refusals, truncations and errors; each is scored as a miss.
- Prices come from models.json: Claude rows use Anthropic list prices (confirm against the Bedrock pricing page), Jev uses TypeSafe's published price, local models cost $0.
- Paid runs so far: $0.7046 in total; each run is capped at $5.00 (guardrails.json).
