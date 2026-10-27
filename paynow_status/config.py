"""Runtime settings, read from the environment with production defaults."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PollerConfig:
    gateway_url: str = "http://fast-gateway.payments.svc:8080"
    status_timeout_s: float = 1.0
    first_check_delay_s: float = 0.5
    max_attempts: int = 5
    backoff_base_s: float = 0.5
    backoff_cap_s: float = 4.0
    retry_budget_ratio: float = 0.1


def load_config(env=os.environ):
    d = PollerConfig()
    return PollerConfig(
        gateway_url=env.get("FAST_GATEWAY_URL", d.gateway_url),
        status_timeout_s=float(env.get("STATUS_TIMEOUT_S", d.status_timeout_s)),
        first_check_delay_s=float(env.get("FIRST_CHECK_DELAY_S", d.first_check_delay_s)),
        max_attempts=int(env.get("MAX_ATTEMPTS", d.max_attempts)),
        backoff_base_s=float(env.get("BACKOFF_BASE_S", d.backoff_base_s)),
        backoff_cap_s=float(env.get("BACKOFF_CAP_S", d.backoff_cap_s)),
        retry_budget_ratio=float(env.get("RETRY_BUDGET_RATIO", d.retry_budget_ratio)),
    )
