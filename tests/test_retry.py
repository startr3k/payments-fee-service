import unittest

from paynow_status.retry import RetryBudget, backoff_delay


class BackoffTest(unittest.TestCase):
    def test_delay_doubles_until_cap(self):
        delays = [backoff_delay(a, 0.5, 4.0, rng=lambda: 1.0) for a in range(1, 6)]
        self.assertEqual([1.0, 2.0, 4.0, 4.0, 4.0], delays)

    def test_jitter_stays_within_bound(self):
        self.assertEqual(0.0, backoff_delay(3, 0.5, 4.0, rng=lambda: 0.0))


class RetryBudgetTest(unittest.TestCase):
    def test_spends_until_empty(self):
        budget = RetryBudget(ratio=0.1, min_tokens=2.0)
        self.assertTrue(budget.try_spend())
        self.assertTrue(budget.try_spend())
        self.assertFalse(budget.try_spend())

    def test_new_payments_refill_budget(self):
        budget = RetryBudget(ratio=0.5, min_tokens=0.0)
        budget.record_attempt()
        budget.record_attempt()
        self.assertTrue(budget.try_spend())


if __name__ == "__main__":
    unittest.main()
