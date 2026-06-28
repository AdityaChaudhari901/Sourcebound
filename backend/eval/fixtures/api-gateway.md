# API Gateway

The API gateway is the single entry point for all external traffic and routes
requests to the internal services.

## Configuration

The gateway listens on port 8443. Set `GATEWAY_TIMEOUT_MS` to control the upstream
request timeout; it defaults to 30000 (30 seconds).

## Authentication

Every external request must include an `X-API-Key` header. Requests without a
valid key are rejected with a 401 response.

## Rate Limiting

Each API key is limited to 100 requests per minute. Exceeding the limit returns a
429 Too Many Requests response.
