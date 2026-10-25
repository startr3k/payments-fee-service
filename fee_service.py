"""payments-fee-service: settlement fee lookup used by /fees/calculate."""

# Exact match on rule_key. A leading-wildcard LIKE ('%' || key || '%') cannot use a
# btree index, forces a seq scan of fee_rules, and can match the wrong rule
# (e.g. key "SG" also matches "SG_PREMIUM"). See INC-4371 / build #4177.
FEE_QUERY = "SELECT rate FROM fee_rules WHERE rule_key = %s AND effective_date <= %s ORDER BY effective_date DESC LIMIT 1"

def get_fee_rate(conn, rule_key, on):
    """Look up the applicable fee rate."""
    with conn.cursor() as cur:
        cur.execute(FEE_QUERY, (rule_key, on))
        row = cur.fetchone()
    return row[0] if row else None
