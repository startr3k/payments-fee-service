# Status-call amplification alert (definition only, not installed)

This document and `status-call-amplification.json` define a proposed alert for the PS-5 failure mode: `paynow-status-service` polling the shared `fast-gateway` far more heavily than the payment volume justifies. Nothing here is deployed. No rule, webhook, notification or automated action is installed or implied.

## What it measures

Per fixed 5-minute bucket, on event counts (not unique payments):

- **Numerator, status calls**: documents in `paynow-gateway-access` with `caller = paynow-status-service` and `route` matching `*status*`. The wildcard is a filter only. Route values are never returned, because routes can embed payment references.
- **Denominator, business submission-request events**: documents with `caller = paynow-payment-service` and `route = /v1/payments`. This includes accepted, failed and rejected attempts. It is not `payment.submitted` alone, which omits unsuccessful requests.
- **Ratio** = status calls / submission-request events.

The same population is seen in app logs as `payment.submitted` 15458 (ACSC) + `payment.failed` 424 (FAILED) + `payment.rejected` 69 (RJCT) = 15951, equal to the gateway count of 15951 in all 97 five-minute buckets on 2026-11-03. Use either representation, never the sum of both. The app categories are alternative outcomes, so a failed or rejected request is not assumed to have a `payment.submitted` precursor. Counts are events, so no unique-payment claim is made.

## Quiet baseline and threshold

Baseline window is `[05:30Z, 10:30Z)` on 2026-11-03 (`[13:30, 18:30)` SGT), 60 complete 5-minute buckets. It was chosen independently of the RCA figures: status timeouts were 0, `payment.failed` was 0 and pool active was 0 throughout, and it ends about 24 minutes before the first timeout at 10:54:47Z.

- Status calls: 18561. Submission-request events: 7381.
- Baseline ratio = 18561 / 7381 = **2.5147** (sum of calls over sum of submissions, not a mean of bucket ratios).
- Threshold = 2 x 2.5147 = **5.0294**.
- **Fire when ratio is strictly greater than 5.0294.** Exactly equal does not fire. The JSON compares `status_calls > 5.0294 * submission_requests`, so there is no division in the comparison.

Limitation: one 8-hour day of lab data, no seasonal or day-of-week baseline. Re-derive the baseline from a fresh quiet window before any real use.

## Query

`status-call-amplification.json` is a complete body for `POST {ES_URL}/paynow-*/_search`, the only endpoint used (`_search`/`_count` on `paynow-*`, read-only). It returns no hits (`size: 0`). It has two parts:

- `baseline_quiet_05_30_to_10_30Z`: the status and submission counts that give 18561 and 7381.
- `buckets_5m`: a 5-minute `date_histogram` (UTC, `min_doc_count: 0`, `extended_bounds`) with per-bucket `status_calls`, `submission_requests`, `status_per_submission` and `exceeds_2x_baseline` (1 = fire, 0 = no).

The query range is fixed to the backtest: `@timestamp` in `[05:30Z, 11:25Z)`. Because the upper bound is exclusive, only completed buckets are returned. For live use, move the upper bound to the last completed 5-minute boundary and keep the 0.0 / 5.0294 constants from a re-derived baseline.

## Evaluation semantics

- Windows are half-open `[start, end)`. A bucket is **evaluated only after it has closed** (at `end`), and only if the data for it are searchable. Bucket start is not the firing time. Evaluation can run no earlier than bucket close plus any ingestion and scheduling delay `d`.
- A terminal partial bucket (one not fully closed) is never evaluated.
- Buckets before the 05:30Z coverage start are unknown, not zero.
- **Zero submissions** in a bucket: the ratio is undefined, so the bucket does not fire (the script yields 0). Treat an unexpected zero as a data or traffic problem to check separately, not as a pass.
- **Missing data** (no gateway documents at all, shard failures, `timed_out: true`): do not evaluate and do not report "healthy". Check `timed_out` and `_shards.failed` on every run.

## Backtest on lab data (actual run of the JSON above)

Run against the lab Elasticsearch with the read-only key: `timed_out: false`, 4/4 shards, 0 failed, `hits.total` 48396, 71 buckets, baseline 18561 / 7381.

| Bucket (UTC) | SGT | Status calls | Submissions | Ratio | Fires |
|---|---|---|---|---|---|
| 11:00-11:05 | 19:00-19:05 | 888 | 266 | 3.338 | no |
| 11:05-11:10 | 19:05-19:10 | 1292 | 299 | 4.321 | no |
| **11:10-11:15** | **19:10-19:15** | **1741** | **305** | **5.708** | **yes** |
| 11:15-11:20 | 19:15-19:20 | 3733 | 332 | 11.244 | yes |
| 11:20-11:25 | 19:20-19:25 | 8657 | 299 | 28.953 | yes |

Every earlier bucket from 05:30Z is below threshold (highest 2.868 at 10:55-11:00Z). The smallest submission count in any bucket is 97, so the zero rule was never triggered.

**Timing.** The first flagged bucket starts at 11:10Z (19:10 SGT) and closes at 11:15Z (19:15 SGT). The earliest completed-bucket evaluation is therefore **19:15 SGT on 3 November, 11 minutes before the 19:26 SGT PS-5 failure-rate alert**. This assumes evaluation at bucket close with the data searchable then (delay `d = 0`). With a delay `d`, evaluation is at 19:15 + d and the lead is 11 minutes - d, so it is earlier only if `d` is under 11 minutes. The historical rule cadence and ingestion delay were not measured, so those are assumptions, not evidence.

## On-call investigation line

If this alert fires, the on-call engineer should manually investigate: which caller is generating the status calls, whether timeout retries or polling intervals are driving the growth, and whether the `gateway.pool` active count is approaching its limit of 64. Do not scale, restart, roll back or change configuration on the strength of this alert alone. The decision to act belongs to a human.
