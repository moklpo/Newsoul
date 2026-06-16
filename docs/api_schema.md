# StratBack India - API Schema (v0.1.0)

This document defines the initial API endpoints for the StratBack India platform.

## Base URL
`/api/v1`

## 1. Authentication (placeholder)
- `POST /auth/login` - Login with credentials.
- `POST /auth/register` - User registration.
- `GET /auth/me` - Get current user profile.

## 2. Historical Data
- `GET /data/symbols` - List available stock symbols (NSE/BSE).
- `GET /data/history` - Fetch OHLCV data for a specific symbol.
  - **Params:**
    - `symbol` (string): e.g., "RELIANCE"
    - `exchange` (string): "NSE" or "BSE"
    - `interval` (string): "1min", "5min", "15min", "1h", "day"
    - `from_date` (ISO 8601)
    - `to_date` (ISO 8601)
- `POST /data/upload` - Upload historical data in CSV/JSON format.
  - **Format Support:** Supports Kite Connect CSV format and generic OHLCV.

## 3. Backtesting Engine
- `GET /strategies` - List available strategy templates or user-defined strategies.
- `POST /backtest/run` - Submit a backtest request.
  - **Body (JSON):**
    ```json
    {
      "strategy_id": "sma_crossover",
      "symbol": "TATASTEEL",
      "exchange": "NSE",
      "interval": "15min",
      "from_date": "2023-01-01",
      "to_date": "2023-12-31",
      "parameters": {
        "short_window": 20,
        "long_window": 50,
        "indicators": ["SMA", "RSI"],
        "stop_loss": 0.02,
        "take_profit": 0.05
      },
      "initial_capital": 100000
    }
    ```
- `GET /backtest/status/{job_id}` - Get the current status of a backtest job (queued, running, completed, failed).
- `GET /backtest/results/{job_id}` - Retrieve the results of a completed backtest.
  - **Returns (JSON):**
    ```json
    {
      "job_id": "uuid",
      "metrics": {
        "cagr": 0.15,
        "sharpe_ratio": 1.2,
        "max_drawdown": -0.08,
        "total_trades": 45,
        "win_rate": 0.65
      },
      "equity_curve": [
        {"date": "2023-01-01", "value": 100000},
        ...
      ],
      "trades": [
        {
          "entry_date": "...",
          "exit_date": "...",
          "entry_price": 100.5,
          "exit_price": 110.2,
          "pnl": 9.7,
          "type": "LONG"
        }
      ]
    }
    ```

## 4. Strategy Marketplace (Future)
- `GET /marketplace/strategies` - List verified strategies available for purchase or free use.
- `POST /marketplace/publish` - Publish a strategy to the marketplace.
