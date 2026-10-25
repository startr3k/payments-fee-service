"""payments-fee-service: settlement fee lookup used by /fees/calculate."""

# Exact match on rule_key so the lookup can use an index. A leading-wildcard LIKE
# ('%' || key || '%') forces a seq scan on fee_rules and can match the wrong rule
# (e.g. key "SG" also matches "SG_PREMIUM"), see INC-4371.
FEE_QUERY = "SELECT rate FROM fee_rules WHERE rule_key = %s AND effective_date <= %s ORDER BY effective_date DESC LIMIT 1"

def get_fee_rate(conn, rule_key, on):
    """Look up the applicable fee rate."""
    with conn.cursor() as cur:
        cur.execute(FEE_QUERY, (rule_key, on))
        row = cur.fetchone()
    return row[0] if row else None
