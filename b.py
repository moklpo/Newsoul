import pandas as pd
import datetime
import time
import requests
import re
import argparse
import sys
from fyers_apiv3 import fyersModel

# --- CONFIGURATION ---
APP_ID = "ESUCFMYU9Q-100"
SECRET_ID = "1ESVP5WA71"
REDIRECT_URL = "https://www.google.com/"
TELEGRAM_TOKEN = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

# AlphaTrend Parameters
COEFF = 1.0
AP = 14
CHANGE_PCT = 1.2  
TOP_COUNT = 20  # Top 20 from Open Price

notified_stocks = {}

# --- INDICATORS (ALPHA TREND) ---
def get_mfi(df, period=14):
    tp = (df['high'] + df['low'] + df['close']) / 3
    mf = tp * df['volume']
    pos_mf = mf.where(tp > tp.shift(1), 0).rolling(window=period).sum()
    neg_mf = mf.where(tp < tp.shift(1), 0).rolling(window=period).sum()
    mfr = pos_mf / neg_mf
    return 100 - (100 / (1 + mfr))

def get_atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return ranges.max(axis=1).rolling(window=period).mean()

def calculate_alphatrend(df):
    df['atr'] = get_atr(df, AP)
    df['mfi'] = get_mfi(df, AP)
    up_t = df['low'] - df['atr'] * COEFF
    down_t = df['high'] + df['atr'] * COEFF
    at = [0.0] * len(df)
    for i in range(1, len(df)):
        if df['mfi'].iloc[i] >= 50:
            at[i] = up_t.iloc[i] if up_t.iloc[i] > at[i-1] else at[i-1]
        else:
            at[i] = down_t.iloc[i] if down_t.iloc[i] < at[i-1] else at[i-1]
    df['at'] = at
    return df

# --- INTRADAY MOVERS FILTER (OPEN VS LTP) ---
def get_filtered_watchlist(full_list):
    """Calculates Change from TODAY'S OPEN instead of Prev Close"""
    try:
        data = {"symbols": ",".join(full_list)}
        quotes = fyers.quotes(data)
        if quotes['s'] != 'ok': return full_list
        
        stock_data = []
        for item in quotes['d']:
            symbol = item['n']
            ltp = item['v']['lp'] 
            open_price = item['v']['op'] # <--- TODAY'S OPEN PRICE
            
            if open_price == 0: continue # Data safety
            
            # Change from Today's Open
            intraday_chg = ((ltp - open_price) / open_price) * 100
            stock_data.append({'symbol': symbol, 'chg': intraday_chg})
        
        df_movers = pd.DataFrame(stock_data)
        # Top 20 stocks that moved most UP from their open
        top_gainers = df_movers.nlargest(TOP_COUNT, 'chg')['symbol'].tolist()
        # Top 20 stocks that moved most DOWN from their open
        top_losers = df_movers.nsmallest(TOP_COUNT, 'chg')['symbol'].tolist()
        
        return list(set(top_gainers + top_losers))
    except Exception as e:
        print(f"⚠️ Filter Error: {e}")
        return full_list

# --- LOGIN & SCAN LOGIC (UNCHANGED) ---
# ... (Baaki saara login aur main loop logic wahi rahega jo pehle diya tha)
