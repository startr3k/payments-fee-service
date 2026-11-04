# PS-5 recurrence sweep

## Summary for bank operations

**What happened.** On 3 November a change to the PayNow status checker (v3.8.0, commit `aad2241`) made it retry a slow payment gateway immediately and without limit. The checker and the payment-submission service share the same gateway connection pool. Status calls grew from about 2.5 per submitted payment to more than 25. The pool of 64 connections filled, and PayNow transfers began failing. The existing alert fired at 19:26 SGT, after the damage had started.

**What could happen again.**

1. **Today, on `main`.** The regression is still in `main` (`fbcddf4` contains `aad2241`). The fix is in open PR #5 (v3.8.1) and is not merged. No deployment record for the fix exists.
2. **After PR #5 merges.** Timeout retries are capped and paced again. Three weaker spots remain: the still-uncapped "pending" polling path (up to 120 calls per payment), a retry budget that is only as shared as the caller makes it, and no alert on status calls per payment.
3. **Process.** No automated test run exists in this repository's pull requests. The only workflow is an AI review that skips drafts. The regression was committed directly to `main` with its safety tests deleted.
4. **Other repositories.** The two other gateways in scope (OCBC and SMB AI gateways) have no retry loops. They have no concurrency limit either. They are not on the payment path, so the risk is low.

**Three guardrails** are proposed in separate draft pull requests. This report does not claim they are merged or deployed.

1. **Retry-policy contract tests plus CI on every PR**, including drafts. They guard the existing timeout retry cap, backoff, ordering and budget.
2. **Review-rule update.** It flags removed or loosened caps, backoff, budgets or timeouts, tests deleted with behaviour changes, and polling increases without peak-load evidence.
3. **Amplification alert** (status calls per submission, strictly more than 2x a quiet baseline). Backtested on 3 November, it would have crossed the threshold at the 19:15 SGT bucket close, 11 minutes before 19:26 SGT. This holds only if the data were searchable and the check was evaluated at that time. Those two assumptions are not proven (see the monitoring section).

## Ranked findings

Score = blast radius (1 to 3: payment-path criticality and shared callers) x likelihood (1 to 3: 3 = code and telemetry confirmation, 2 = code-only confirmation of a combination, 1 = a single ingredient). Ingredients: (a) retry or poll loop without cap, growing wait or budget; (b) immediate retry on timeout or connection error; (c) shared resource without per-caller limit; (d) no calls-per-business-transaction monitoring; (e) safety tests deleted or weakened with a behaviour change, with passing or insufficient CI. Order is by score, then by strength of evidence. Rows 2 to 4 tie at 6, and row 1 is the only confirmed case.

| Rank | Repo and location | Evidence | Ingredients present | Missing guard | Recommended fix | Blast radius | Likelihood | Score |
|---|---|---|---|---|---|---|---|---|
| 1 | `payments-fee-service` `paynow_status/poller.py:30-42` at `aad2241d1b8410c9fe4239ff1d43dbe6fb655b37` (v3.8.0, 2026-11-02T11:20:00+08:00); still on `main` | Code: the timeout handler is `log; continue` (lines 35-38) with no sleep, cap or budget. The loop is bounded only by a 30 s deadline. History: the same commit deleted `paynow_status/retry.py` and `tests/test_retry.py` and rewrote the cap test to expect 120 calls. Simulation: 30 calls and 0 sleeps in an always-timeout run, against 5 calls before the commit. Telemetry: status calls per submission rose from a baseline of 2.5147 to 25-29. The shared `fast-gateway` pool (64 slots) reached 64 active at 11:29:55Z (19:29:55 SGT). Deployed to prod-sg 2026-11-03 14:10:22 SGT | (a), (b), (c), (e) confirmed. (d) was also missing (no alert measured the ratio) | Retry cap, backoff and budget; tests that fail when they are removed; a ratio alert | Merge PR #5 (v3.8.1 restores them). Add the three guardrails | 3 | 3 | **9** |
| 2 | `payments-fee-service` `paynow_status/poller.py:54-56` and `paynow_status/config.py:10-11` at fix `98cef9cc327c7d16d442589ef268dc205ea9c2d4` | Code: a pending status is polled every constant 0.25 s until a 30 s deadline, which is up to 120 calls per payment. A v3.7.2 payment made at most 5. The setting has no jitter and no validation of environment overrides. Simulated: 120 calls in an always-pending run. No telemetry shows this path causing harm | (a) in the pending path, (c) shared gateway | A cap or growing wait on pending polls; a peak-load check on the 5 to 120 change | Decide on a cap or backoff for pending polls. Require a stated calls-per-payment figure at peak (review rule) | 3 | 2 | **6** |
| 3 | `payments-fee-service` `paynow_status/poller.py:25` and `paynow_status/retry.py:11-34` at the fix | Code: the default `RetryBudget` is built per `StatusPoller`. This repository has no production entry point, so whether one budget is shared is unknown. `tests/test_poller.py` still has the `aad2241` rewrite. The poller-level budget-exhaustion test and jitter and growth tests through the poller are absent | (c) budget scope, (e) test gap | A shared budget (or proof of one) and poller-level tests | Retry-policy contract tests (guardrail 1). Confirm in the deploying service that one budget is injected. Do not assume a singleton | 3 | 2 | **6** |
| 4 | Whole status-to-gateway path (no repo holds the alert); alert inventory in the three repositories, Jira and Sentry | Inventory: the PS-5 alert watches failed transfers over 5 minutes (outcome). The only alert definition in the repositories (OCBC `kibana/alert-rule.json`) watches mobile failure rate in a different index. None measures status calls per submission, retries, or pool use. Backtest: a ratio above 2x baseline crosses at the 11:10-11:15Z bucket (5.708 against 5.0294), about 11 minutes before 19:26 SGT, under stated assumptions | (d), with residual (a) and (c) from rows 2 and 3 | Calls-per-submission alert, with a manual on-call investigation line | Amplification alert (guardrail 3) | 3 | 2 | **6** |
| 5 | `payments-fee-service` `.github/workflows/droid-review.yml:10`, `.factory/skills/review-guidelines/SKILL.md:5-8`, history of `aad2241` | The only workflow is an AI review and runs no tests. It skips draft PRs. No PR or workflow run exists for `aad2241`, which went directly to `main`. The review guideline asks for backoff, a cap and a stated peak expectation. It does not mention removing safeguards, deleting tests or peak-load evidence | (e) | A CI test run on every PR; review rules on removed safeguards and deleted tests | Test workflow on every PR (guardrail 1); review rule update (guardrail 2); branch protection (a human decision, not done here) | 3 | 1 | **3** |
| 6 | `ocbc-payments-aiops` `gateway/gateway.py:212-215`, `gateway/config.json:6` at `82a67ebd04948de25560cac18f091ca1e8160ab1` | Code: a thread per request, no cap, no queue, one upstream key per route. There is a single `urlopen` with a 600 s timeout and no retry loop. The gateway is an AI model gateway and is not on the PayNow path. No logs for it exist in `paynow-*` | (c) locally only | Concurrency or per-caller limit. An external provider limit is unknown | Optional: add a concurrency cap if usage grows. Low priority | 1 | 1 | **1** |
| 7 | `smb-payments-eod` `gateway/gateway.py:223-233`, `gateway/config.json` at `1fb7fe8be2c6c2c3f414fef6cf4bc66ac5805c3b` | Same pattern. The 600 s timeout is hard-coded at `gateway.py:170` and is not configurable. No retry loop. `smb_eod/` has no network code | (c) locally only | Same as row 6 | Same as row 6 | 1 | 1 | **1** |

No finding is listed for retry loops that were inspected and found safe (for example the OCBC and SMB tool and test timeouts and the stream relay loops). They are in the code evidence as negative results. The AI gateways get no telemetry-based rating because they have no logs in the data.

## Historical PS-5, current fix and residual risk

- **Historical regression (`aad2241`, v3.8.0, authored 2026-11-02T11:20:00+08:00, direct commit on `main`).** (a) The timeout path has no cap or budget at `poller.py:35-38`. The loop is bounded only by the 30 s deadline at `poller.py:30`. (b) The timeout path continues immediately, with no sleep. (c) Both services call the same `fast-gateway`. The pool had 64 slots, a sampled maximum of 64 active at 11:29:55Z and 83 of 960 samples at or above 32. No per-caller pool field exists. (e) The same commit deleted `retry.py` and all four tests in `tests/test_retry.py`. It also deleted `test_stops_retrying_when_budget_is_spent` and rewrote `test_gives_up_after_max_attempts` to `test_gives_up_at_deadline`, which asserts 120 calls. The suite went from 9 tests to 4.
- **Current fix (`98cef9c`, v3.8.1, open PR #5, not merged, no deployment record).** Timeout retries are capped at 5 retries (6 calls), preceded by a jittered capped wait, and spend from a budget. `retry.py` and `tests/test_retry.py` are restored byte for byte, and `tests/test_timeout_pacing.py` is added. This does not touch the pending-poll behaviour or the budget scope. Connection errors other than timeouts are not caught by the poller and propagate (they are not retried).
- **Residual risks:** rows 2 to 5 above.
- **RCA attribution.** The commit message of `98cef9c` and the user-supplied RCA say calls per payment rose from about 2.6 to 22 and that 424 transfers failed. These are historical claims. This sweep did not rely on them. The gateway had 424 HTTP 504 responses to payment-service, equal to 424 `payment.failed` events. The independently measured ratio was 2.5147 (quiet) and 25-29 (incident). Jira PS-5 was read through the read-only connector: that read showed zero comments and an alert-only description, while an earlier readiness read reported four RCA comments. This discrepancy is unresolved. Nothing here claims that Jira supplied the RCA.

## Sweep dimensions

Evidence stays outside the pull request, in the mission folder `/Users/dan/.factory/missions/d40f2c97-fe91-4e0b-b6d9-39e4a5f019be/evidence/`. Section numbers refer to those files.

### Code (`code.md`)

All tracked source and configuration in the three repositories was searched for retry, poll, timeout, deadline, attempt, backoff, budget, semaphore, pool, worker, queue, lock and rate-limit patterns. Every hit was classified. The payments poller has a production caller outside this repository (not present here). Introducing commits and dates came from blame and parent diffs. Both `gateway/gateway.py` and `gateway/config.json` were read in full in OCBC and SMB. Result: the only (a)+(b) loop is `aad2241`. (c) exists as unbounded thread-per-request design in both AI gateways, and as the shared FAST pool in the PayNow path. Code.md sections 3 to 6.

### Telemetry (`telemetry.md`)

- Window: gateway, app and Kafka events cover only 2026-11-03 05:30:04Z to 13:30:01Z (13:30 to 21:30 SGT). That is 96 complete five-minute buckets plus a 1.2-second terminal partial bucket at 13:30Z, which is excluded from baselines and flags. Deployment records cover 2026-10-28T02:30:00Z to 2026-11-03T11:45:31Z.
- Totals: 236,755 documents (gateway 136,344; app 98,965; Kafka lag 1,440; deployments 6).
- Callers: two, `paynow-status-service` (120,393 calls) and `paynow-payment-service` (15,951 calls, all `/v1/payments`).
- Denominator: business submission-request events are the 15,951 gateway events. They reconcile with the app events `payment.submitted` 15,458 (ACSC) + `payment.failed` 424 (FAILED) + `payment.rejected` 69 (RJCT) = 15,951, in every one of the 97 buckets. These are alternative representations that must not be added together. They are event counts, not unique payments.
- Baseline: the quiet window is [05:30,10:30)Z, which has 60 buckets, 18,561 status calls and 7,381 submissions, so the ratio is 2.5147 and the threshold is above 5.0294. The first flagged complete bucket is 11:10Z (5.708). In all, 13 complete buckets (11:10Z to 12:10Z) are flagged. The peak is 29.21 at 12:00Z. Nothing is flagged before 11:10Z.
- Retries: `status.timeout` events number 81,524. The tagged attempt ordinal ranges from 1 to 39. A mean of 14.84 retry-tagged ordinals per timeout event is event-weighted, and no per-payment retry distribution is possible without identifiers.
- Pool: 960 samples fall in the 96 complete buckets. The pool size is always 64. Climb above 1 begins at 11:06:55Z, 83 samples are at or above 32, and 1 sample reaches 64 (11:29:55Z).
- Unavailable: per-caller pool occupancy, queue or wait fields, ingestion timestamps, any day other than 3 November, and any other gateway or caller.

### Process (`process.md`)

- Test erosion: `aad2241` is the only commit in the three repositories that deleted or weakened tests together with a behaviour change. `53bf953` deleted a test because the code it covered was retired. OCBC and SMB have no test deletions.
- CI: payments has one workflow, an AI review that skips drafts and runs no tests. SMB has a CI workflow that runs pytest on pull requests, including drafts, but whether it ran was not verified. OCBC has no workflows. No unittest run exists in payments history.
- Review guidance: covered above (row 5).
- Deployments: 5 deploys and 1 restart. The `aad2241` deploy (2026-11-03 14:10:22 SGT) was in a quiet period before the evening peak. Deploy 5 (notification-sender, 18:45 SGT) was in the ramp. The restart (fast-gateway, 19:45 SGT) was an incident action. Deploys 1 to 3 pre-date telemetry coverage, so quiet or peak cannot be judged.

### Monitoring (`monitoring.md`)

- Existing alerts: the PS-5 failure-rate alert (Jira) and the OCBC Kibana rule. Neither covers amplification. Sentry showed one unresolved timeout issue (count 311). The read connector exposes no alert rules.
- Backtest: fixed five-minute buckets close at 11:15Z (19:15 SGT) with a ratio of 1741/305 = 5.708. A rolling one-minute model first crosses at 11:13Z (19:13 SGT). The lead over 19:26 SGT is 11 minutes (fixed) or 13 minutes (rolling), minus any searchability and scheduling delay. The delay and the historical alert cadence are assumptions, not evidence.
- No alert was installed.

## Coverage and limits

| Item | Examined |
|---|---|
| `payments-fee-service` | HEAD `98cef9cc327c7d16d442589ef268dc205ea9c2d4` (fix branch), `main` `fbcddf4a8890ac7911b09497db115e02db3be431`, regression `aad2241d1b8410c9fe4239ff1d43dbe6fb655b37`. Tracked files (15) and full history (27 commits on `main`) |
| `ocbc-payments-aiops` | `82a67ebd04948de25560cac18f091ca1e8160ab1`, 56 tracked files and 3 commits. Local `main` is one commit ahead of origin. `gateway/gateway.py` and `gateway/config.json` read |
| `smb-payments-eod` | `1fb7fe8be2c6c2c3f414fef6cf4bc66ac5805c3b`, 95 tracked files and 12 commits. `gateway/gateway.py` and `gateway/config.json` read |
| Excluded | OCBC `seed/` and `reports/sample/` (never used), SMB `golden/` data, binaries and `*.ndjson`, caches and `.git` internals, an unrelated untracked payments report (not read) |
| Not run | OCBC and SMB test suites, application code, demo or operations scripts. Their CI runs on GitHub were not queried |
| Telemetry | `paynow-*` via `_search` and `_count` only. Gateway, app and Kafka events: 2026-11-03 13:30 to 21:30 SGT (8 hours). Earlier hours, other days and weekdays: not observed. Empty buckets before 05:30Z are unknown, not zero |
| Callers | Exactly two seen: `paynow-status-service` and `paynow-payment-service`. Nothing is claimed about other callers or about AI gateway traffic |
| Unavailable | Per-caller pool use, queue and wait data, ingestion lag, rule cadence for the PS-5 alert, a multi-day baseline, the production entry point that constructs the poller, and whether SMB CI actually ran |
| Not claimed | Unique-payment counts, per-payment retry counts, a caller-to-payment join, or any external control on the AI gateways |

## Reproducing the evidence

Mission-local evidence (not part of this pull request): `/Users/dan/.factory/missions/d40f2c97-fe91-4e0b-b6d9-39e4a5f019be/evidence/code.md`, `telemetry.md`, `process.md`, `monitoring.md`. Each file holds the full query bodies, counts and bounds.

Three citations, re-run before publication and giving the same results:

1. **Elasticsearch query.** `POST $ES_URL/paynow-*/_count` with body `{}` returns `count: 236755`. Pool saturation (telemetry Q11): `POST $ES_URL/paynow-*/_search` with
   `{"size":0,"track_total_hits":true,"query":{"bool":{"filter":[{"term":{"_index":"paynow-app-logs"}},{"term":{"event":"gateway.pool"}}]}},"aggs":{"full":{"filter":{"range":{"pool_active":{"gte":64}}}},"ge90":{"filter":{"range":{"pool_active":{"gte":58}}}},"ge50":{"filter":{"range":{"pool_active":{"gte":32}}}},"first_full":{"filter":{"range":{"pool_active":{"gte":64}}},"aggs":{"mn":{"min":{"field":"@timestamp"}}}}}}`
   returned total 960, `full` 1, `ge90` 5, `ge50` 83 and first full sample `2026-11-03T11:29:55.000Z`, with `timed_out:false` and 4 of 4 shards. Use `Authorization: ApiKey` from the read-only credential file. Do not print it.
2. **Pinned source line.** `git show aad2241d1b8410c9fe4239ff1d43dbe6fb655b37:paynow_status/poller.py | nl -ba | sed -n 35,38p` shows `except GatewayTimeoutError:`, the warning log, and `continue` with no sleep. Compare `git show 98cef9cc327c7d16d442589ef268dc205ea9c2d4:paynow_status/poller.py | nl -ba | sed -n 40,53p` for the cap at line 43, budget at line 47 and wait at line 51.
3. **Git history.** `git log --diff-filter=D --name-status --format='%h %ad' --date=iso-strict aad2241 -1 -- paynow_status/retry.py tests/test_retry.py` prints `aad2241 2026-11-02T11:20:00+08:00` with `D paynow_status/retry.py` and `D tests/test_retry.py`. `git show --stat aad2241` reports 6 files changed, 34 insertions and 104 deletions.

Times in ES are UTC. SGT is UTC+8. 19:26 SGT is 11:26:00Z. All windows are half-open, `[start, end)`.

## Read-only attestation

The investigation was read-only. It ran no restart, scale, rollback, deploy, service start or stop, demo or operations script, Jira or Sentry write, and no Elasticsearch call other than `_search` and `_count` on `paynow-*`. It did not change code, branches or Git configuration in `ocbc-payments-aiops` or `smb-payments-eod`, did not push or merge to `main`, and did not copy customer or payment identifiers into any artifact. The only writes are the explicitly authorised branch deliverables: this report on `docs/ps5-recurrence-sweep` and the three separate draft guardrail branches, each with its own pull request, plus mission-local evidence files outside the repositories.
