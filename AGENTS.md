# payments-fee-service — AGENTS.md

## What this is
Settlement fee calculation service (prod-sg). Computes fees from `fee_rules`, emits settlement
records to Kafka topic `settlement.fees`. Downstream: fee-aggregator consumer, Qlik Replicate
task REP_SG_SETTLEMENT → Cloudera staging → risk dashboards.

## Topology & tools (lab)
- Elasticsearch: http://localhost:9200 — index `payments-logs-*` (app, deploy, kafka-lag, replicate telemetry). Use MCP tool `search_es`.
- Postgres: postgresql://ocbc_ro:readonlypass@localhost:5432/settlement (READ-ONLY user). `psql -c "EXPLAIN ANALYZE ..."`.
- Kafka (Redpanda): `rpk topic describe settlement.fees`, `rpk group describe fee-aggregator`.
- Jenkins (mock): GET http://localhost:8085/api/jobs/payments-fee-service-deploy/builds — deploy history with commits.
- Rollback: POST http://localhost:8085/api/jobs/rollback-<build>/run — **policy: ask** (needs approver).

## Rules for agents
- Investigation is READ-ONLY. Never mutate prod systems directly; recovery goes through the Jenkins rollback job (policy-gated).
- `kubectl delete`, `DROP`, `TRUNCATE` are blocked by org policy — do not attempt.
- Root-cause claims must cite evidence: ES query + timestamp, commit SHA, query plan, lag numbers.
- Known incident family: deploy-induced latency → check deploy marker in ES, then fee_rules query plan, then Kafka lag.
