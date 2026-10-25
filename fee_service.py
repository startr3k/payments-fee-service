"""payments-fee-service: settlement fee lookup used by /fees/calculate."""
import re

FEE_QUERY_INDEXED = "SELECT rate FROM fee_rules WHERE rule_key = %s AND effective_date <= %s ORDER BY effective_date DESC LIMIT 1"
FEE_QUERY_LIKE = "SELECT rate FROM fee_rules WHERE rule_key LIKE '%%' || %s || '%%' AND effective_date <= %s ORDER BY effective_date DESC LIMIT 1"

def get_fee_rate(conn, rule_key, on):
    """Look up the applicable fee rate. BAD-COMMIT a1b9c2f switched to the LIKE variant,
    which defeats the (planned) index and forces a seq scan on 200k rows."""
    sql = FEE_QUERY_LIKE if _bad_path_enabled() else FEE_QUERY_INDEXED
    with conn.cursor() as cur:
        cur.execute(sql, (rule_key, on))
        row = cur.fetchone()
    return row[0] if row else None

def _bad_path_enabled():
    # deploy flag from build #4177; rollback restores the equality path
    import os
    return os.environ.get("FEE_LIKE_ROLLOUT", "on") == "on"
