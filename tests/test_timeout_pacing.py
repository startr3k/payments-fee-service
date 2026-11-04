"""Regression tests for PS-5: timed-out status checks must wait, and must stop.

Release 3.8.0 retried a timed-out status check at once with no wait and no
cap, so an evening-peak slowdown of fast-gateway became a retry storm that
failed 424 PayNow transfers. These tests pin the fix: every retry waits
(first a backoff sleep, then the next call), and a payment gives up after a
bounded number of retries instead of hammering the gateway for the full
deadline.
"""
import unittest

from paynow_status.config import PollerConfig
from paynow_status.gateway_client import GatewayTimeoutError
from paynow_status.poller import UNKNOWN, StatusPoller


class Clock:
    """Manual clock; records every sleep and lets the fake client burn time."""

    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.sleeps.append(seconds)

    def advance(self, seconds):
        self.now += seconds


class AlwaysTimeoutClient:
    """Gateway that never answers: each check burns its full timeout, then fails."""

    def __init__(self, clock):
        self._clock = clock
        self.calls = 0

    def get_status(self, payment_ref, timeout):
        self.calls += 1
        self._clock.advance(timeout)
        raise GatewayTimeoutError(
            f"status check for {payment_ref} exceeded {int(timeout * 1000)}ms")


def _poller(clock):
    client = AlwaysTimeoutClient(clock)
    poller = StatusPoller(client, PollerConfig(), sleep=clock.sleep, clock=clock)
    return client, poller


class TimeoutPacingTest(unittest.TestCase):
    def test_gives_up_after_bounded_retries(self):
        clock = Clock()
        client, poller = _poller(clock)

        result = poller.poll_until_final("PN1")

        self.assertEqual(UNKNOWN, result.status)
        # One first check plus at most 5 retries, not ~30 back-to-back
        # checks across the 30 s deadline.
        self.assertLessEqual(client.calls, 6)

    def test_every_retry_waits_before_hitting_the_gateway_again(self):
        clock = Clock()
        client, poller = _poller(clock)

        poller.poll_until_final("PN1")

        # Every call after the first is a retry and must be preceded by a
        # wait; the final timed-out attempt itself is not followed by one.
        self.assertEqual(client.calls - 1, len(clock.sleeps))


if __name__ == "__main__":
    unittest.main()
