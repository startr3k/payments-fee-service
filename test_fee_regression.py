import os
import unittest
from unittest.mock import MagicMock, patch

import fee_service


class FeeQueryRegression(unittest.TestCase):
    """Keep the default lookup indexed while preserving explicit rollout overrides."""

    def setUp(self):
        env_patch = patch.dict(os.environ, {}, clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = (0.015,)

    def test_lookup_uses_equality_not_like(self):
        self.assertFalse(fee_service._bad_path_enabled())
        rate = fee_service.get_fee_rate(self.conn, "FEE_0137_9", "2026-10-26")
        self.assertEqual(rate, 0.015)
        self.cursor.execute.assert_called_once_with(
            fee_service.FEE_QUERY_INDEXED, ("FEE_0137_9", "2026-10-26")
        )

    def test_explicit_on_preserves_like_override(self):
        os.environ["FEE_LIKE_ROLLOUT"] = "on"
        self.assertTrue(fee_service._bad_path_enabled())
        fee_service.get_fee_rate(self.conn, "FEE_0137_9", "2026-10-26")
        self.cursor.execute.assert_called_once_with(
            fee_service.FEE_QUERY_LIKE, ("FEE_0137_9", "2026-10-26")
        )

    def test_explicit_off_uses_equality(self):
        os.environ["FEE_LIKE_ROLLOUT"] = "off"
        self.assertFalse(fee_service._bad_path_enabled())
        fee_service.get_fee_rate(self.conn, "FEE_0137_9", "2026-10-26")
        self.cursor.execute.assert_called_once_with(
            fee_service.FEE_QUERY_INDEXED, ("FEE_0137_9", "2026-10-26")
        )

    def test_missing_fee_rule_returns_none(self):
        self.cursor.fetchone.return_value = None
        self.assertIsNone(
            fee_service.get_fee_rate(self.conn, "FEE_MISSING", "2026-10-26")
        )


if __name__ == "__main__":
    unittest.main()
