# HTTP API

## POST /checkout

```json
{
  "orderId": "A-1001",
  "customer": {
    "name": "Rina",
    "tier": "gold"
  },
  "items": [
    { "sku": "SKU-1", "qty": 2, "unitPrice": 25.00 }
  ]
}
```

Response:

```json
{
  "ok": true,
  "subtotal": 50.0,
  "total": 47.5,
  "discount_rate": 0.05,
  "tier_used": "GOLD"
}
```

Accepted `tier` spellings: `standard`/`basic`/`free`, `gold`/`premium`,
`platinum`/`enterprise` (case insensitive).

## GET /benefits?tier=gold

```json
{ "rate": 0.05 }
```