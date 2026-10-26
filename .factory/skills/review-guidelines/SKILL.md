# Review guidelines — payments-fee-service (OCBC lab)

Additional checks for this payments codebase:

- Any query-path change must show index coverage (EXPLAIN output or a migration adding the supporting index). A sequential scan on `fee_rules` is a known incident cause (INC-4371).
- Feature flags touching fee calculation must default to "off" and state a rollout plan in the PR description.
- Financial record handling: no Kafka offset resets, no non-idempotent replays of settlement records.
- Fee-rule lookup must preserve exact-key semantics: rule keys contain underscores; LIKE patterns treat them as wildcards.
- Migrations must be idempotent (IF NOT EXISTS / IF EXISTS) and safe to run online.
