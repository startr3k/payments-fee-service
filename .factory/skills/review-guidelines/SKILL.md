# Review guidelines: payments-fee-service (paynow-status-service)

Additional checks for this payments codebase:

- Every call to `fast-gateway` needs a timeout. Retries need exponential
  backoff with jitter, a maximum attempt count and a test that proves both.
- Changes to polling intervals or retry behaviour must state the expected
  change in calls per payment at peak traffic in the PR description.
- Flag any change that removes or loosens a retry safeguard: a lower or
  removed maximum attempt count or retry cap, a smaller backoff base, cap or
  jitter, a removed or enlarged retry budget, or a longer or removed timeout.
  Also flag replacing a bounded retry loop with a loop bounded only by a
  wall-clock deadline, and any retry path that can run again without waiting.
  Request changes unless the PR keeps an equivalent per-payment cap, a
  backoff wait and a shared retry budget, and says which test proves each.
- Flag tests deleted or weakened in the same change as the behaviour they
  covered. Deleting a test for a retry cap, backoff or retry budget while the
  matching code is changed or removed needs a replacement test for the new
  behaviour, or an explicit reason why the safeguard is no longer needed.
- When a change raises polling frequency (a shorter interval, a removed
  initial delay, or retries without a wait), the PR description must show
  worst-case calls per payment and calls per second at peak traffic across all
  replicas, and the effect on shared `fast-gateway` capacity (it also carries
  payment submissions). A unit test alone is not peak-load evidence. If it is
  missing, ask for it before approving.
- Never log or test with real customer identifiers, account numbers or NRICs.
- Payment status handling must stay idempotent: the same status received
  twice must not notify the customer twice.
- Configuration defaults must be safe for production; risky behaviour sits
  behind a flag that defaults to off.
