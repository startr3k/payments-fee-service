"""Polls fast-gateway until a PayNow transfer reaches a final status."""
import logging
import time
from dataclasses import dataclass

from .gateway_client import FINAL_STATUSES, GatewayTimeoutError
from .retry import RetryBudget, backoff_delay

log = logging.getLogger(__name__)

# The app shows "processing" and the customer is notified when the status arrives.
UNKNOWN = "UNKNOWN"


@dataclass
class PollResult:
    status: str
    attempts: int


class StatusPoller:
    def __init__(self, client, config, budget=None, sleep=time.sleep, clock=time.monotonic):
        self._client = client
        self._config = config
        self._budget = budget or RetryBudget(config.retry_budget_ratio)
        self._sleep = sleep
        self._clock = clock

    def poll_until_final(self, payment_ref):
        self._budget.record_attempt()
        deadline = self._clock() + self._config.deadline_s
        attempt = 0
        timeouts = 0
        while self._clock() < deadline:
            attempt += 1
            try:
                status = self._client.get_status(
                    payment_ref, timeout=self._config.status_timeout_s)
            except GatewayTimeoutError:
                timeouts += 1
                log.warning("status check timed out", exc_info=True,
                            extra={"payment_ref": payment_ref, "attempt": attempt})
                if timeouts > self._config.max_retries:
                    log.warning("gateway retries exhausted; leaving payment pending",
                                extra={"payment_ref": payment_ref, "attempt": attempt})
                    return PollResult(UNKNOWN, attempt)
                if not self._budget.try_spend():
                    log.warning("retry budget exhausted; leaving payment pending",
                                extra={"payment_ref": payment_ref, "attempt": attempt})
                    return PollResult(UNKNOWN, attempt)
                self._sleep(backoff_delay(timeouts, self._config.backoff_base_s,
                                          self._config.backoff_cap_s))
                continue
            if status in FINAL_STATUSES:
                return PollResult(status, attempt)
            self._sleep(self._config.poll_interval_s)
        return PollResult(UNKNOWN, attempt)
