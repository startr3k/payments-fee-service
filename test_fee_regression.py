import unittest, os
os.environ["FEE_LIKE_ROLLOUT"] = "on"  # deploy env of build #4177 must not re-enable the LIKE path
import fee_service


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return self.conn.row


class _FakeConn:
    def __init__(self, row):
        self.row = row
        self.executed = []

    def cursor(self):
        return _FakeCursor(self)


class FeeQueryRegression(unittest.TestCase):
    """Deterministic, no DB needed."""

    def test_lookup_uses_equality_not_like(self):
        conn = _FakeConn(row=(0.0125,))
        fee_service.get_fee_rate(conn, "FEE_0137_9", "2026-10-26")
        sql, params = conn.executed[0]
        self.assertNotIn("LIKE", sql.upper(),
            "fee-rule lookup regressed to LIKE scan — causes seq scan on fee_rules (INC-4371)")
        self.assertIn("rule_key = %s", sql)
        self.assertEqual(params, ("FEE_0137_9", "2026-10-26"))

    def test_returns_rate_or_none(self):
        self.assertEqual(fee_service.get_fee_rate(_FakeConn(row=(0.0125,)), "K", "2026-10-26"), 0.0125)
        self.assertIsNone(fee_service.get_fee_rate(_FakeConn(row=None), "K", "2026-10-26"))


if __name__ == "__main__":
    unittest.main()
