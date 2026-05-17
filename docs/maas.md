# Model-as-a-Service (MaaS)

The MaaS module provides LLM inference usage metering for an inference-as-a-service backend. Users create API keys via the web UI, and an inference backend authenticates each request with a user's API key, validates it, and reports usage via a REST API.

## Screenshots

### User page
Shows API keys, usage summary, and recent usage records for a user.

### API key creation
API keys are shown in plaintext only once at creation time with a copy-to-clipboard button.

### Provider management
Staff can manage inference providers, each with a secret key used to associate usage with the correct provider.

## Features

- **API key management**: Create, view, and revoke API keys with optional expiration dates
- **Provider management**: Admin-managed providers with secret keys
- **Usage recording**: Record inference usage with tokens, cost, latency, and model info
- **Key validation**: Pre-inference endpoint to verify both user key and provider
- **Show-once keys**: API keys are displayed only once at creation
- **User isolation**: Users can only see their own keys; staff/admin can browse any user

## How It Works

```
End User (Bearer key) → Inference Backend → Portal API
                                               ├── Verify key + provider
                                              └── POST usage record
```

The inference backend receives the user's Bearer token, forwards it to the portal for validation, and includes the provider's secret key to associate the usage with the correct provider.

---

## API Reference

All API endpoints return JSON. Authentication uses `Authorization: Bearer <api_key>`.

### Verify Key + Provider

Validate a user's API key and provider before running inference.

**POST** `/api/maas/verify/`

**Headers:**
- `Authorization: Bearer <user_api_key>`

**Request body:**
```json
{
    "provider_key": "<provider-secret-key>"
}
```

**Response 200:**
```json
{
    "valid": true,
    "user": "username",
    "expires_at": "2026-12-31T23:59:59Z",
    "provider": {
        "id": 1,
        "name": "OpenAI Production",
        "url": "https://inference.example.com"
    }
}
```

**Response 401** (invalid/expired user key):
```json
{ "detail": "Invalid API key" }
```

**Response 400** (invalid provider key):
```json
{ "error": "Invalid provider key" }
```

**cURL:**
```bash
curl -X POST http://localhost/api/maas/verify/ \
  -H "Authorization: Bearer <user-api-key-value>" \
  -H "Content-Type: application/json" \
  -d '{"provider_key": "<provider-secret-key>"}'
```

### Record Usage

Record the usage for a completed inference request.

**POST** `/api/maas/usage/`

**Headers:**
- `Authorization: Bearer <user_api_key>`

**Request body:**
```json
{
    "provider_key": "<provider-secret-key>",
    "model": "gpt-4o",
    "endpoint": "/v1/chat/completions",
    "input_tokens": 150,
    "output_tokens": 320,
    "cost": 0.00475,
    "latency_ms": 450,
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `provider_key` | Yes | string | Secret key identifying the provider |
| `model` | Yes | string | Model name (e.g., `gpt-4o`, `claude-3`) |
| `endpoint` | Yes | string | API endpoint used (e.g., `/v1/chat/completions`) |
| `input_tokens` | Yes | integer | Number of input tokens consumed |
| `output_tokens` | Yes | integer | Number of output tokens generated |
| `cost` | No | number | Cost of the request (if applicable) |
| `latency_ms` | Yes | integer | Response time in milliseconds |
| `request_id` | No | string | Unique request identifier (auto-generated if omitted) |

**Response 201:**
```json
{
    "id": 1,
    "user": "username",
    "provider_name": "OpenAI Production",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "model": "gpt-4o",
    "endpoint": "/v1/chat/completions",
    "input_tokens": 150,
    "output_tokens": 320,
    "cost": 0.00475,
    "latency_ms": 450,
    "created_at": "2026-05-16T12:00:00Z"
}
```

**cURL:**
```bash
curl -X POST http://localhost/api/maas/usage/ \
  -H "Authorization: Bearer <user-api-key-value>" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_key": "<provider-secret-key>",
    "model": "gpt-4o",
    "endpoint": "/v1/chat/completions",
    "input_tokens": 150,
    "output_tokens": 320,
    "cost": 0.00475,
    "latency_ms": 450
  }'
```

### Query Usage

Retrieve usage records for the authenticated user.

**GET** `/api/maas/usage/`

**Headers:**
- `Authorization: Bearer <user_api_key>`

**Query parameters:**
| Parameter | Description |
|-----------|-------------|
| `model` | Filter by model name |
| `start` | Filter by start date (ISO format) |
| `end` | Filter by end date (ISO format) |

**Response 200:**
```json
[
    {
        "id": 1,
        "user": "username",
        "provider_name": "OpenAI Production",
        "request_id": "550e8400-...",
        "model": "gpt-4o",
        "endpoint": "/v1/chat/completions",
        "input_tokens": 150,
        "output_tokens": 320,
        "cost": 0.00475,
        "latency_ms": 450,
        "created_at": "2026-05-16T12:00:00Z"
    }
]
```

**cURL:**
```bash
curl -H "Authorization: Bearer <user-api-key-value>" \
  "http://localhost/api/maas/usage/?model=gpt-4o&start=2026-05-01"
```

### Revoke Key (Public)

**POST** `/api/maas/key/revoke/`

A public endpoint that revokes a key by presenting it in the auth header. Always returns `200` — never reveals whether the key existed — to prevent key enumeration.

**Headers:**
- `Authorization: Bearer <key_to_revoke>`

**Response 200:**
```json
{}
```

**cURL:**
```bash
curl -X POST -H "Authorization: Bearer <key-to-revoke>" \
  http://localhost/api/maas/key/revoke/
```

## Requirements

No external dependencies beyond Django REST Framework (already included in the project).
