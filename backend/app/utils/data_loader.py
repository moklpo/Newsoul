import pandas as pd
import pathlib
import vectorbt as vbt

class DataLoader:
    def __init__(self, data_path: str = "/home/team/shared/data/historical"):
        self.data_path = pathlib.Path(data_path)

    def load_symbol_data(self, symbol: str, exchange: str = "NSE", granularity: str = "1min"):
        file_path = self.data_path / granularity / f"{symbol}.parquet"
        if not file_path.exists():
            # For development, return empty or raise error
            # In a real scenario, we'd fetch or use mock data
            raise FileNotFoundError(f"Data for {symbol} not found at {file_path}")
        
        df = pd.read_parquet(file_path)
        return df

    def get_vbt_data(self, symbol: str, exchange: str = "NSE", granularity: str = "1min"):
        df = self.load_symbol_data(symbol, exchange, granularity)
        return vbt.Data.from_pandas(df)
