# Token economics

Only one user action — a *genuinely new* question — is allowed to spend tokens
by default. Everything else is designed around a zero-token path.

## Budgets

| Event                                      | Budget       | How                                        |
|--------------------------------------------|--------------|--------------------------------------------|
| Upload or connect data                     | 0            | Profiling & schema inference are deterministic |
| Open a page, filter, paginate, refresh     | 0            | Stored plans + result cache; LLM unreachable from this path |
| Scheduled report or alert                  | 0            | Re-executes plans, no narration            |
| Repeated or similar question               | 0            | T0 cache, T1 templates, T2 grammar         |
| Follow-up ("now by month")                 | 0 common, ≤300 otherwise | IR patches, current plan only  |
| New question needing the cloud LLM         | ≤ 920 (800 in / 120 out) | Schema slice + 3 examples      |
| Repair after a failed validation           | ≤ 250, one retry | Error + failing fragment only          |
| "Write it up" narration                    | ~300, optional | Precomputed facts only                   |

## Enforcement

1. **CI budget tests** — each prompt template is rendered against the largest
   fixture schema. The build fails if a rendered prompt exceeds its tier's
   budget. See `packages/llm_gateway/tests/test_prompt_budget.py`.

2. **Per-tenant caps** — monthly soft and hard limits. On the hard limit, the
   compile service falls back to T3 (local model) or returns the closest
   matching templates as clickable suggestions.

3. **Prompt prefix caching** — the static system prompt is byte-identical
   across calls, so providers that discount cached input tokens charge less
   for most of each prompt.

4. **Metering** — every LLM call logs tenant, tier, input and output tokens
   and outcome. TPAQ and cascade hit rates come from these logs and are shown
   in the admin console.

## Target

Target to validate in the beta: after one month of use, at least 70% of a
tenant's questions resolve at T0–T2 with no LLM call. The admin console
reports the real figure continuously.
