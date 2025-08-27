# API Reference

## Overview

The Alphamind API provides REST endpoints for interacting with the TAO20 index token system, including minting, redemption, and index management operations.

## Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://api.alphamind.xyz`

## Authentication

All API requests require authentication using Bittensor hotkey signatures:

```bash
Authorization: Bearer <bittensor_signature>
```

## Endpoints

### Index Information

#### Get Index Composition

```http
GET /api/v1/index/composition
```

**Response:**
```json
{
  "subnets": [1, 2, 3, 4, 5],
  "weights": [20, 20, 20, 20, 20],
  "total_weight": 100,
  "last_rebalance": "2024-01-15T00:00:00Z"
}
```

#### Get Current NAV

```http
GET /api/v1/index/nav
```

**Response:**
```json
{
  "nav": 1.0234,
  "timestamp": "2024-01-15T12:00:00Z",
  "components": [
    {
      "subnet": 1,
      "price": 1.0,
      "weight": 0.2,
      "contribution": 0.2
    }
  ]
}
```

### Minting Operations

#### Initiate Mint

```http
POST /api/v1/mint/initiate
```

**Request Body:**
```json
{
  "amount": "1000000000000000000",
  "subnet_tokens": [
    {
      "subnet": 1,
      "amount": "200000000000000000"
    }
  ],
  "miner_hotkey": "0x1234...",
  "signature": "0xabcd..."
}
```

**Response:**
```json
{
  "request_id": "req_123456",
  "status": "pending",
  "estimated_tao20": "1000000000000000000",
  "expires_at": "2024-01-15T12:05:00Z"
}
```

#### Get Mint Status

```http
GET /api/v1/mint/status/{request_id}
```

**Response:**
```json
{
  "request_id": "req_123456",
  "status": "completed",
  "tao20_amount": "1000000000000000000",
  "transaction_hash": "0x1234...",
  "completed_at": "2024-01-15T12:03:00Z"
}
```

### Redemption Operations

#### Initiate Redemption

```http
POST /api/v1/redeem/initiate
```

**Request Body:**
```json
{
  "tao20_amount": "1000000000000000000",
  "miner_hotkey": "0x1234...",
  "signature": "0xabcd..."
}
```

**Response:**
```json
{
  "request_id": "req_789012",
  "status": "pending",
  "estimated_subnet_tokens": [
    {
      "subnet": 1,
      "amount": "200000000000000000"
    }
  ],
  "expires_at": "2024-01-15T12:05:00Z"
}
```

#### Get Redemption Status

```http
GET /api/v1/redeem/status/{request_id}
```

**Response:**
```json
{
  "request_id": "req_789012",
  "status": "completed",
  "subnet_tokens": [
    {
      "subnet": 1,
      "amount": "200000000000000000",
      "transaction_hash": "0x5678..."
    }
  ],
  "completed_at": "2024-01-15T12:03:00Z"
}
```

### Validator Operations

#### Submit Attestation

```http
POST /api/v1/validator/attest
```

**Request Body:**
```json
{
  "request_id": "req_123456",
  "operation": "mint",
  "attestation": "0xabcd...",
  "validator_hotkey": "0x1234...",
  "signature": "0xefgh..."
}
```

**Response:**
```json
{
  "status": "accepted",
  "attestation_id": "att_123456"
}
```

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "INVALID_SIGNATURE",
    "message": "Invalid Bittensor signature",
    "details": "Signature verification failed"
  }
}
```

### Common Error Codes

- `INVALID_SIGNATURE` - Invalid Bittensor hotkey signature
- `INSUFFICIENT_BALANCE` - Insufficient token balance
- `REQUEST_EXPIRED` - Request has expired
- `INVALID_AMOUNT` - Invalid token amount
- `SUBNET_NOT_SUPPORTED` - Subnet not in index
- `RATE_LIMITED` - Too many requests

## Rate Limits

- **Public endpoints**: 100 requests per minute
- **Authenticated endpoints**: 1000 requests per minute
- **Validator endpoints**: 5000 requests per minute

## WebSocket API

For real-time updates, connect to the WebSocket endpoint:

```javascript
const ws = new WebSocket('wss://api.alphamind.xyz/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

### WebSocket Events

- `nav_update` - NAV value changes
- `mint_completed` - Mint operation completed
- `redeem_completed` - Redemption operation completed
- `index_rebalance` - Index composition changed
