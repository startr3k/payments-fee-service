# payments-fee-service

This repository is named after the fee lookup service it used to host. It now
hosts **paynow-status-service**.

## paynow-status-service

When a customer sends a PayNow transfer, `paynow-payment-service` submits it to
the FAST network through `fast-gateway`. This service then asks `fast-gateway`
for the transfer's status until it is final (`ACSC` settled or `RJCT`
rejected) and tells the app, which shows the customer the result.

```
mobile app → paynow-payment-service → fast-gateway → FAST network
                     ↓                     ↑
             paynow-status-service ────────┘  (status checks)
                     ↓
       Kafka payments.notifications → notification-sender → push
```

## Status codes

| Code | Meaning | What the customer sees |
|---|---|---|
| `ACSC` | Settled at the beneficiary bank | "Transfer successful" |
| `RJCT` | Rejected, with an ISO 20022 reason code | "Transfer failed" and the reason |
| `PDNG` | Still in flight | "Processing" |
| `UNKNOWN` | No final status in time | "Processing"; a push notification follows |

## Run the tests

```bash
python3 -m unittest discover -s tests -t . -v
```

No dependencies beyond the Python 3.10+ standard library.
