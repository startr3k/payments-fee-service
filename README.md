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

## Run the tests

```bash
python3 -m unittest discover -s tests -t . -v
```

No dependencies beyond the Python 3.10+ standard library.
