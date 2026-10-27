"""Thin client for fast-gateway's payment status endpoint."""
import json
import urllib.error
import urllib.request

# ISO 20022 transaction status codes returned by the FAST network.
FINAL_STATUSES = {"ACSC", "RJCT"}  # settled / rejected by the beneficiary bank
PENDING = "PDNG"


class GatewayError(Exception):
    pass


class GatewayTimeoutError(GatewayError):
    pass


class FastGatewayClient:
    def __init__(self, base_url, opener=urllib.request.urlopen):
        self._base_url = base_url.rstrip("/")
        self._open = opener

    def get_status(self, payment_ref, timeout):
        url = f"{self._base_url}/v1/payments/{payment_ref}/status"
        try:
            with self._open(url, timeout=timeout) as resp:
                body = json.load(resp)
        except TimeoutError as exc:
            raise GatewayTimeoutError(
                f"status check for {payment_ref} exceeded {int(timeout * 1000)}ms") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise GatewayTimeoutError(
                    f"status check for {payment_ref} exceeded {int(timeout * 1000)}ms") from exc
            raise GatewayError(str(exc)) from exc
        return body["status"]
