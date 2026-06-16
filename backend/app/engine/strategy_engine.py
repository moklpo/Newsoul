import vectorbt as vbt
import pandas as pd
from app.utils.data_loader import DataLoader

class StrategyEngine:
    def __init__(self, data_loader: DataLoader = None):
        self.data_loader = data_loader or DataLoader()

    def run_sma_crossover(self, symbol: str, fast_window: int, slow_window: int, exchange: str = "NSE", granularity: str = "1min"):
        try:
            df = self.data_loader.load_symbol_data(symbol, exchange, granularity)
        except FileNotFoundError:
            # Mock data for demonstration if file not found
            # This should be replaced with real data fetching/loading
            import numpy as np
            dates = pd.date_range(start="2023-01-01", periods=1000, freq="1T")
            price = 100 + np.cumsum(np.random.randn(1000) * 0.1)
            df = pd.DataFrame({
                'open': price,
                'high': price + 0.1,
                'low': price - 0.1,
                'close': price,
                'volume': np.random.randint(100, 1000, 1000)
            }, index=dates)

        close = df['close']
        fast_ma = vbt.MA.run(close, fast_window)
        slow_ma = vbt.MA.run(close, slow_window)

        entries = fast_ma.ma_crossed_above(slow_ma)
        exits = fast_ma.ma_crossed_below(slow_ma)

        portfolio = vbt.Portfolio.from_signals(close, entries, exits, init_cash=100000)
        
        return self._format_results(portfolio)

    def _format_results(self, portfolio):
        stats = portfolio.stats()
        
        # Extract metrics
        metrics = {
            "cagr": stats['Ann. Return [%]'] / 100,
            "sharpe_ratio": stats['Sharpe Ratio'],
            "max_drawdown": stats['Max. Drawdown [%]'] / 100,
            "total_trades": stats['Total Trades'],
            "win_rate": stats['Win Rate [%]'] / 100,
            "total_return": stats['Total Return [%]'] / 100
        }

        # Equity curve
        equity_curve = portfolio.value().reset_index()
        equity_curve.columns = ['date', 'value']
        equity_curve['date'] = equity_curve['date'].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Trades
        trades = portfolio.trades.records()
        formatted_trades = []
        # vectorbt trades records have entry_idx, exit_idx, etc.
        # We need to map them back to dates and prices
        # For simplicity in MVP, we'll just return a few or summary
        
        return {
            "metrics": metrics,
            "equity_curve": equity_curve.to_dict(orient='records'),
            "trades": formatted_trades # Placeholder for more detailed trade info
        }
