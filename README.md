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
# Edit .env with your API keys (see API Keys section below)
```

## API Keys

| Key | Required | Source | Purpose |
|-----|----------|--------|---------|
| `KALSHI_API_KEY` | Yes | [Kalshi](https://kalshi.com/sign-up) | Market data |
| `KALSHI_PRIVATE_KEY` | Yes | Kalshi API settings | RSA-PSS signing |
| `ANTHROPIC_API_KEY` | Yes | [Anthropic](https://console.anthropic.com/) | LLM probability estimation |
| `OPENWEATHER_API_KEY` | Yes | [OpenWeatherMap](https://openweathermap.org/api) | Climate market research |
| `FRED_API_KEY` | Yes | [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) | Economics market research |
| `ODDS_API_KEY` | Optional | [The Odds API](https://the-odds-api.com/) | Sports odds/scores |
| `TAVILY_API_KEY` | Optional | [Tavily](https://tavily.com/) | Web search for sports context |

Sports research uses both The Odds API (structured odds data) and Tavily (web search context). If either key is missing, that data source is skipped gracefully.

## Running a Scan

### Option 1: CLI script

```bash
source .venv/bin/activate
python scripts/run_scan.py
```

### Option 2: API server

```bash
# Start server
uvicorn src.main:app --reload

# Trigger scan via API
curl -X POST http://localhost:8000/api/v1/scans

# Check scan status
curl http://localhost:8000/api/v1/scans/{scan_id}

# View recommendations
curl http://localhost:8000/api/v1/recommendations
```

### Supported Categories

The scanner automatically categorizes Kalshi markets into:

| Category | Data Sources | Example Markets |
|----------|-------------|-----------------|
| `climate` | OpenWeatherMap | NYC high temperature, snowfall |
| `economics` | FRED | CPI, unemployment, GDP |
| `sports` | The Odds API + Tavily | NBA, NFL, MLB, NHL, UFC, NASCAR |

Categories can be configured via the settings API:

```bash
# View current settings
curl http://localhost:8000/api/v1/settings

# Enable/disable categories
curl -X PATCH http://localhost:8000/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"categories": ["climate", "economics", "sports"]}'
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
