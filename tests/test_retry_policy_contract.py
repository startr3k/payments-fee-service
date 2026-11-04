"""Contract for the PS-5 timeout-retry policy of StatusPoller.

Pins four behaviours with fake time, a fake gateway and controlled random
draws, so nothing here sleeps or touches the network:

* timeouts are retried at most five times (six calls) however much deadline
  and retry budget remain;
* each retry waits first, using a jittered backoff that grows with the retry
  number and is capped;
* the wait comes before the next gateway call, including when the timeout
  reaches the poller through the real client's connection-error handling;
* retries spend the retry budget, and an exhausted budget stops retries
  without denying a new payment its first attempt.

The cap applies to timeout retries only. Pending (PDNG) polling is not
covered here.
"""
import contextlib
import dataclasses
import importlib
import itertools
import logging
import unittest
import urllib.error

from paynow_status import poller as poller_module
from paynow_status.config import PollerConfig
from paynow_status.gateway_client import FastGatewayClient, GatewayTimeoutError
from paynow_status.poller import UNKNOWN, StatusPoller

MAX_TIMEOUT_RETRIES = 5
BASE_S = 0.5
CAP_S = 4.0

# Long enough that neither the deadline nor the default budget ends a
# timeout-only poll before the retry cap does.
ROOMY = dataclasses.replace(PollerConfig(), deadline_s=600.0)


class World:
    """Fake time plus an ordered log of gateway calls and waits."""

    def __init__(self):
        self.now = 0.0
        self.events = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.events.append(("wait", seconds))
        self.now += seconds

    def calls(self):
        return sum(1 for kind, _ in self.events if kind == "call")

    def waits(self):
        return [value for kind, value in self.events if kind == "wait"]

    def kinds(self):
        return [kind for kind, _ in self.events]


class TimingOutClient:
    """Every status check burns its whole timeout and then fails."""

    def __init__(self, world):
        self._world = world

    def get_status(self, payment_ref, timeout):
        self._world.events.append(("call", timeout))
        self._world.now += timeout
        raise GatewayTimeoutError("timed out")


def _slow_opener(world):
    """urlopen stand-in: the socket times out the way urllib reports it."""

    def opener(url, timeout):
        world.events.append(("call", timeout))
        world.now += timeout
        raise urllib.error.URLError(TimeoutError("timed out"))

    return opener


def _poller(world, client=None, config=ROOMY, **kwargs):
    client = client or TimingOutClient(world)
    try:
        return StatusPoller(client, config, sleep=world.sleep, clock=world.clock,
                            **kwargs)
    except TypeError as exc:
        raise AssertionError(f"StatusPoller does not accept {sorted(kwargs)}: {exc}")


@contextlib.contextmanager
def _draws(*values):
    """Route the poller's backoff through controlled random draws.

    The helper binds its default random source when it is defined, so
    patching the global random module would not reach it; the poller's own
    reference is wrapped instead. Yields the (attempt, base, cap) calls.
    """
    seen = []
    real = getattr(poller_module, "backoff_delay", None)
    if real is None:
        yield seen
        return
    source = itertools.cycle(values)

    def spy(attempt, base_s, cap_s, **kwargs):
        seen.append((attempt, base_s, cap_s))
        return real(attempt, base_s, cap_s, rng=lambda: next(source))

    original = poller_module.backoff_delay
    poller_module.backoff_delay = spy
    try:
        yield seen
    finally:
        poller_module.backoff_delay = original


def _retry_module(test):
    try:
        return importlib.import_module("paynow_status.retry")
    except ImportError:
        test.fail("paynow_status.retry (backoff and retry budget) does not exist")


class QuietLogsMixin:
    def setUp(self):
        super().setUp()
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)


class TimeoutRetryCapTest(QuietLogsMixin, unittest.TestCase):
    def test_default_cap_is_five_retries(self):
        self.assertEqual(MAX_TIMEOUT_RETRIES,
                         getattr(PollerConfig(), "max_retries", None))

    def test_timeouts_stop_after_first_call_plus_five_retries(self):
        world = World()
        result = _poller(world).poll_until_final("PN1")

        self.assertEqual(UNKNOWN, result.status)
        self.assertEqual(1 + MAX_TIMEOUT_RETRIES, world.calls())
        self.assertEqual(1 + MAX_TIMEOUT_RETRIES, result.attempts)

    def test_cap_is_not_the_deadline_or_the_budget(self):
        world = World()
        _poller(world).poll_until_final("PN1")

        # Deadline headroom: far from the 600 s limit when polling stopped.
        self.assertLess(world.now, ROOMY.deadline_s / 4)

    def test_cap_holds_with_a_budget_that_never_runs_out(self):
        retry = _retry_module(self)
        budget = retry.RetryBudget(0.0, min_tokens=100.0, max_tokens=100.0)
        world = World()
        _poller(world, budget=budget).poll_until_final("PN1")

        self.assertEqual(1 + MAX_TIMEOUT_RETRIES, world.calls())


class JitteredBackoffTest(QuietLogsMixin, unittest.TestCase):
    def test_envelope_grows_each_retry_then_stays_at_the_cap(self):
        retry = _retry_module(self)
        half = [retry.backoff_delay(n, BASE_S, CAP_S, rng=lambda: 0.5)
                for n in range(1, 7)]

        self.assertEqual([0.5, 1.0, 2.0, 2.0, 2.0, 2.0], half)
        full = [retry.backoff_delay(n, BASE_S, CAP_S, rng=lambda: 1.0)
                for n in range(1, 7)]
        self.assertEqual([1.0, 2.0, 4.0, 4.0, 4.0, 4.0], full)

    def test_draw_scales_the_wait_inside_the_envelope(self):
        retry = _retry_module(self)

        def delay(draw):
            return retry.backoff_delay(3, BASE_S, CAP_S, rng=lambda: draw)

        self.assertEqual(0.0, delay(0.0))
        self.assertEqual(1.0, delay(0.25))
        self.assertEqual(3.0, delay(0.75))

    def test_poller_waits_follow_the_helper_with_config_values(self):
        world = World()
        draws = (0.9, 0.1, 0.8, 0.2, 0.5)
        with _draws(*draws) as seen:
            _poller(world).poll_until_final("PN1")

        envelopes = [min(CAP_S, BASE_S * 2 ** n) for n in range(1, 6)]
        self.assertEqual([(n, BASE_S, CAP_S) for n in range(1, 6)], seen)
        self.assertEqual([d * e for d, e in zip(draws, envelopes)], world.waits())

    def test_poller_waits_grow_then_hit_the_cap(self):
        world = World()
        with _draws(0.5):
            _poller(world).poll_until_final("PN1")

        self.assertEqual([0.5, 1.0, 2.0, 2.0, 2.0], world.waits())
        self.assertTrue(all(w <= CAP_S for w in world.waits()))


class WaitBeforeRetryTest(QuietLogsMixin, unittest.TestCase):
    EXPECTED = ["call", "wait"] * MAX_TIMEOUT_RETRIES + ["call"]

    def test_each_timeout_is_followed_by_a_wait_before_the_next_call(self):
        world = World()
        with _draws(0.5):
            _poller(world).poll_until_final("PN1")

        self.assertEqual(self.EXPECTED, world.kinds())

    def test_wait_is_policy_derived_and_not_zero(self):
        world = World()
        with _draws(0.5):
            _poller(world).poll_until_final("PN1")

        self.assertEqual(MAX_TIMEOUT_RETRIES, len(world.waits()))
        self.assertTrue(all(w > 0 for w in world.waits()))

    def test_connection_error_timeout_waits_before_retrying(self):
        world = World()
        client = FastGatewayClient("http://gateway.invalid", opener=_slow_opener(world))
        with _draws(0.5):
            result = _poller(world, client=client).poll_until_final("PN1")

        self.assertEqual(UNKNOWN, result.status)
        self.assertEqual(self.EXPECTED, world.kinds())


class SpyBudget:
    """Real RetryBudget that records every spend decision."""

    @staticmethod
    def build(test, ratio, min_tokens, max_tokens=100.0):
        retry = _retry_module(test)

        class Spy(retry.RetryBudget):
            def __init__(self):
                super().__init__(ratio, min_tokens=min_tokens, max_tokens=max_tokens)
                self.spends = []
                self.attempts = 0

            def record_attempt(self):
                self.attempts += 1
                super().record_attempt()

            def try_spend(self):
                allowed = super().try_spend()
                self.spends.append(allowed)
                return allowed

        return Spy()


class RetryBudgetTest(QuietLogsMixin, unittest.TestCase):
    def test_each_timeout_retry_spends_the_budget(self):
        budget = SpyBudget.build(self, 0.0, min_tokens=50.0)
        world = World()
        _poller(world, budget=budget).poll_until_final("PN1")

        self.assertEqual(1, budget.attempts)
        self.assertEqual([True] * MAX_TIMEOUT_RETRIES, budget.spends)

    def test_exhausted_budget_stops_retries_before_the_cap(self):
        budget = SpyBudget.build(self, 0.0, min_tokens=2.0)
        world = World()
        result = _poller(world, budget=budget).poll_until_final("PN1")

        self.assertEqual(UNKNOWN, result.status)
        self.assertEqual([True, True, False], budget.spends)
        self.assertEqual(3, world.calls())
        self.assertEqual(2, len(world.waits()))

    def test_empty_budget_still_allows_the_first_attempt_of_a_new_payment(self):
        budget = SpyBudget.build(self, 0.0, min_tokens=0.0)
        world = World()
        poller = _poller(world, budget=budget)

        for ref in ("PN1", "PN2"):
            before = world.calls()
            result = poller.poll_until_final(ref)
            self.assertEqual(UNKNOWN, result.status)
            self.assertEqual(1, world.calls() - before)

        self.assertEqual([], world.waits())
        self.assertEqual([False, False], budget.spends)

    def test_budget_is_shared_when_the_caller_shares_it(self):
        budget = SpyBudget.build(self, 0.0, min_tokens=7.0)
        world = World()
        first = _poller(world, budget=budget)
        second = _poller(world, budget=budget)

        first.poll_until_final("PN1")
        second.poll_until_final("PN2")

        # 5 retries for the first payment leave 2 for the second.
        self.assertEqual([True] * 5 + [True, True, False], budget.spends)


if __name__ == "__main__":
    unittest.main()
