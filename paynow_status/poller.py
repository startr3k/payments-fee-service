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
    def __init__(self, client, config, budget=None, sleep=time.sleep):
        self._client = client
        self._config = config
        self._budget = budget or RetryBudget(config.retry_budget_ratio)
        self._sleep = sleep

    def poll_until_final(self, payment_ref):
        self._budget.record_attempt()
        delay = self._config.first_check_delay_s
        for attempt in range(1, self._config.max_attempts + 1):
            self._sleep(delay)
            try:
                status = self._client.get_status(
                    payment_ref, timeout=self._config.status_timeout_s)
            except GatewayTimeoutError:
                if not self._budget.try_spend():
                    log.warning("retry budget exhausted; leaving payment pending",
                                extra={"payment_ref": payment_ref, "attempt": attempt})
                    return PollResult(UNKNOWN, attempt)
            else:
                if status in FINAL_STATUSES:
                    return PollResult(status, attempt)
            delay = backoff_delay(attempt, self._config.backoff_base_s,
                                  self._config.backoff_cap_s)
        return PollResult(UNKNOWN, self._config.max_attempts)
