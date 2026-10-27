# AGENTS.md

This repository hosts **paynow-status-service** (see README.md). The repository
name is historical.

## Working on the code

- Python 3.10+, standard library only.
- Run the tests with `python3 -m unittest discover -s tests -t . -v`.
- Changes go on a branch and land through a reviewed pull request.

## Production context (prod-sg)

- Deployed by the Jenkins job `paynow-status-service-deploy`, 6 replicas.
- Calls `fast-gateway`, which also carries payment submissions from
  `paynow-payment-service`.
- Logs, gateway access logs, deploy records and Kafka consumer lag are shipped
  to Elasticsearch in `paynow-*` indices. Timestamps are stored in UTC; the
  bank reports times in SGT (UTC+8).
- Errors are reported to the Sentry project `paynow-status-service`.

## Lab access on this computer

- Elasticsearch: `ES_URL` and `ES_API_KEY` are in
  `~/.config/elastic/paynow-readonly.env`. The key is read-only.

## Rules for agents

- Investigations are read-only. Never restart, scale, roll back or deploy.
- Ask a human before changing code. Never push to `main`.
- Never copy customer identifiers into tickets, pull requests or commits.
