import unittest, os
os.environ["FEE_LIKE_ROLLOUT"] = "on"  # simulate deployed state of build #4177
import fee_service

class FeeQueryRegression(unittest.TestCase):
    """Fails on build #4177 (LIKE path), passes once the fix restores the equality path.
    This is the regression test the overnight fix PR adds — deterministic, no DB needed."""

    def test_lookup_uses_equality_not_like(self):
        # The deployed code path must not contain LIKE for rule_key matching.
        deployed = fee_service.FEE_QUERY_LIKE if fee_service._bad_path_enabled() else fee_service.FEE_QUERY_INDEXED
        self.assertNotIn("LIKE", deployed,
            "fee-rule lookup regressed to LIKE scan — causes seq scan on fee_rules (INC-4371)")

if __name__ == "__main__":
    unittest.main()
