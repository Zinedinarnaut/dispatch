# Dispatch

Dispatch is a FastAPI-powered service that aggregates product data from multiple streetwear and sneaker retailers. The initial release focuses on Complex Shop, Universal Store, and GOAT, normalising product information into a consistent schema for downstream consumers.

## Features

- **Unified API** for product discovery with provider filtering and search queries.
- **Site-specific scrapers** that pull rich metadata (pricing, imagery, brand, release information and more).
- **Security guardrails** including API-key authentication and in-memory rate limiting.
- **Telemetry pipeline** that records API usage and scraper performance events with optional external forwarding.
- **Configurable runtime** through environment variables for tuning timeouts, concurrency and security settings.

## Getting Started

### Prerequisites

- Python 3.10+
- Optional: a virtual environment (recommended)

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Running the API

```bash
uvicorn dispatch.api.main:app --reload
```

The service exposes the following useful endpoints:

- `GET /health` – service heartbeat.
- `GET /api/v1/providers` – available scraping providers.
- `GET /api/v1/products` – fetch products. Requires an `X-Dispatch-Key` header when API keys are configured.

#### Example request

```bash
curl -H "X-Dispatch-Key: <your-key>" \
     'http://localhost:8000/api/v1/products?providers=goat&query=jordan&limit=10'
```

## Configuration

Environment variables accepted by Dispatch:

| Variable | Description | Default |
| --- | --- | --- |
| `APP_NAME` | Application name | `Dispatch` |
| `ENVIRONMENT` | Deployment environment | `development` |
| `API_V1_PREFIX` | Base path for versioned routes | `/api/v1` |
| `DEFAULT_TIMEOUT_SECONDS` | HTTP timeout for scrapers | `10` |
| `MAX_CONNECTIONS` | Max concurrent connections | `10` |
| `USER_AGENT` | User agent for outbound requests | Desktop Chrome string |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | `*` |
| `TELEMETRY_ENDPOINT` | Optional HTTP endpoint to forward telemetry JSON events | unset |
| `API_KEYS` | Comma-separated API keys | unset |
| `REQUEST_RATE_PER_MINUTE` | Requests per minute per client | `60` |

Create a `.env` file in the repository root or export environment variables before starting the server.

## Telemetry

Telemetry events are queued in-memory and optionally forwarded to an HTTP endpoint defined by `TELEMETRY_ENDPOINT`. Events include scraper success/error counts and API usage metadata, enabling centralised monitoring.

## Security

Dispatch enforces rate limiting on all routes and optional API-key authentication on privileged product endpoints. Additional measures such as TLS termination and reverse-proxy hardening should be configured at deployment time.

## Development

Run the API locally with live reload:

```bash
uvicorn dispatch.api.main:app --reload
```

Execute tests (if/when added):

```bash
pytest
```

## Project Structure

```
src/dispatch/
├── api/                # FastAPI application and routers
├── core/               # Configuration and HTTP helpers
├── scraping/           # Scraper abstractions and provider implementations
├── security/           # Authentication and rate limiting utilities
└── telemetry/          # Event definitions and forwarding logic
```

## Roadmap

- Expand provider support beyond the initial three stores.
- Add persistence for historical price tracking.
- Introduce background jobs for scheduled scraping runs.

See the [CHANGELOG](CHANGELOG.md) for release notes.
