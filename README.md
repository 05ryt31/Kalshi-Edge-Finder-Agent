# Kalshi Edge Finder Agent

AI agent for finding information edges in Kalshi prediction markets.

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start server
uvicorn src.main:app --reload

# Run manual scan
python scripts/run_scan.py
```

## API

Base URL: `http://localhost:8000/api/v1`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/markets` | GET | List filtered markets |
| `/markets/{ticker}` | GET | Get market details |
| `/scans` | POST | Start a scan |
| `/scans` | GET | List scans |
| `/scans/{id}` | GET | Scan details |
| `/recommendations` | GET | List recommendations |
| `/recommendations/{id}` | GET | Recommendation details |
| `/recommendations/{id}` | PATCH | Update status |
| `/settings` | GET/PATCH | View/update settings |
| `/stats/summary` | GET | Performance stats |

## Testing

```bash
pytest
pytest --cov=src --cov-report=html
```
