# StratBack India - UI/UX Design Notes (v0.1.0)

This document outlines the layout and user flow for the StratBack India trader dashboard.

## 1. Design Principles
- **Clarity:** Financial data should be easy to read and interpret.
- **Speed:** The transition from inputting parameters to seeing results should be seamless.
- **Interactivity:** Charts should be zoomable and trades should be inspectable on the chart.

## 2. Layout Structure (The Dashboard)

### Sidebar (Left)
- **Projects/Strategies:** List of saved strategy configurations.
- **Marketplace:** Quick link to the strategy marketplace.
- **Settings:** API keys (Zerodha Kite), platform preferences.

### Main Content Area (Center/Right)

#### Top Bar: Strategy Configuration
- **Symbol Search:** Search for NSE/BSE stocks (e.g., RELIANCE).
- **Timeframe:** Dropdown (1m, 5m, 15m, 1h, 1d).
- **Date Range:** Start and End date pickers.
- **Strategy Selector:** Dropdown (e.g., SMA Crossover, RSI Mean Reversion, Custom Script).
- **Parameters Panel:** Dynamic inputs based on the selected strategy (e.g., Fast Period, Slow Period).
- **Run Button:** High-visibility button to trigger the backtest.

#### Middle Section: Summary Metrics (Cards)
- **Total PnL:** (Currency & Percentage)
- **CAGR:** Compound Annual Growth Rate.
- **Sharpe Ratio:** Risk-adjusted return metric.
- **Max Drawdown:** The largest peak-to-trough decline.
- **Win Rate:** Percentage of profitable trades.

#### Bottom Section: Visualization (Tabs)
1. **Equity Curve:** High-performance line chart showing capital growth over time.
2. **Candlestick Chart:** Interactive OHLC chart with Buy/Sell markers overlaid at trade execution points.
3. **Trades List:** Searchable/Sortable table showing entry/exit dates, prices, and individual PnL.
4. **Logs:** Raw output from the backtesting engine (useful for debugging custom scripts).

## 3. User Flow
1. **User logs in** and is greeted by the dashboard with a default strategy (e.g., SMA Crossover).
2. **User selects a symbol** (e.g., HDFCBANK) and adjusts parameters using sliders.
3. **User clicks "Run Backtest"**.
4. **Platform shows a loading state** (simulating the engine processing data).
5. **Dashboard updates** with metrics and charts once the results are received from the API.
6. **User analyzes the equity curve** and clicks on specific trade markers to see details.
7. **User saves the configuration** if satisfied with the results.

## 4. Tech Stack (Frontend)
- **React:** For UI components.
- **Tailwind CSS:** For styling.
- **Recharts or Lightweight Charts (TradingView):** For high-fidelity financial charting.
- **Lucide React:** For iconography.
