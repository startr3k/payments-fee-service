import unittest

from paynow_status.config import PollerConfig
from paynow_status.gateway_client import GatewayTimeoutError
from paynow_status.poller import UNKNOWN, StatusPoller
from paynow_status.retry import RetryBudget


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get_status(self, payment_ref, timeout):
        self.calls += 1
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


def poller(client, budget=None):
    return StatusPoller(client, PollerConfig(), budget=budget, sleep=lambda s: None)


class StatusPollerTest(unittest.TestCase):
    def test_returns_final_status_once_gateway_settles(self):
        client = FakeClient(["PDNG", "ACSC"])
        result = poller(client).poll_until_final("PN1")
        self.assertEqual(("ACSC", 2), (result.status, result.attempts))

    def test_returns_rejection(self):
        result = poller(FakeClient(["RJCT"])).poll_until_final("PN1")
        self.assertEqual("RJCT", result.status)

    def test_gives_up_after_max_attempts(self):
        client = FakeClient(["PDNG"])
        result = poller(client).poll_until_final("PN1")
        self.assertEqual(UNKNOWN, result.status)
        self.assertEqual(PollerConfig().max_attempts, client.calls)

    def test_recovers_from_a_single_timeout(self):
        client = FakeClient([GatewayTimeoutError("slow"), "ACSC"])
        self.assertEqual("ACSC", poller(client).poll_until_final("PN1").status)

    def test_stops_retrying_when_budget_is_spent(self):
        client = FakeClient([GatewayTimeoutError("slow")])
        budget = RetryBudget(ratio=0.0, min_tokens=1.0)
        result = poller(client, budget).poll_until_final("PN1")
        self.assertEqual(UNKNOWN, result.status)
        self.assertEqual(2, client.calls)


if __name__ == "__main__":
    unittest.main()
