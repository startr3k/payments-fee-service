import unittest

from paynow_status.config import PollerConfig
from paynow_status.gateway_client import GatewayTimeoutError
from paynow_status.poller import UNKNOWN, StatusPoller


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


class FakeClock:
    """Advances by one poll interval per sleep, so deadlines are reached quickly."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def poller(client, clock=None):
    clock = clock or FakeClock()
    return StatusPoller(client, PollerConfig(), sleep=clock.sleep, clock=clock)


class StatusPollerTest(unittest.TestCase):
    def test_returns_final_status_once_gateway_settles(self):
        client = FakeClient(["PDNG", "ACSC"])
        result = poller(client).poll_until_final("PN1")
        self.assertEqual(("ACSC", 2), (result.status, result.attempts))

    def test_returns_rejection(self):
        result = poller(FakeClient(["RJCT"])).poll_until_final("PN1")
        self.assertEqual("RJCT", result.status)

    def test_gives_up_at_deadline(self):
        client = FakeClient(["PDNG"])
        result = poller(client).poll_until_final("PN1")
        self.assertEqual(UNKNOWN, result.status)
        self.assertEqual(120, client.calls)  # 30s deadline / 250ms interval

    def test_recovers_from_a_single_timeout(self):
        client = FakeClient([GatewayTimeoutError("slow"), "ACSC"])
        self.assertEqual("ACSC", poller(client).poll_until_final("PN1").status)


if __name__ == "__main__":
    unittest.main()
