# Polling by default; webhooks an optional switch

Owner decision: Plaid and Teller are polled every 2 minutes with automatic back-off, SimpleFIN 4 times a day. Webhooks need a public endpoint (Tailscale Funnel to an isolated receiver) and only ever wake a sync; they stay off by default so a home install needs no inbound exposure.
