# Review guidelines: payments-fee-service (paynow-status-service)

Additional checks for this payments codebase:

- Every call to `fast-gateway` needs a timeout. Retries need exponential
  backoff with jitter, a maximum attempt count and a test that proves both.
- Changes to polling intervals or retry behaviour must state the expected
  change in calls per payment at peak traffic in the PR description.
- Never log or test with real customer identifiers, account numbers or NRICs.
- Payment status handling must stay idempotent: the same status received
  twice must not notify the customer twice.
- Configuration defaults must be safe for production; risky behaviour sits
  behind a flag that defaults to off.
