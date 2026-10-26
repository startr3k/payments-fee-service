CREATE INDEX IF NOT EXISTS idx_fee_rule_key_date ON fee_rules(rule_key, effective_date DESC);
