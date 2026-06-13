"""
╔══════════════════════════════════════════════════════════════╗
║          TRADING BOT v3 — MAXIMUM ACCURACY EDITION          ║
║                                                              ║
║  Filters stacked (hardest to pass = best stock only):        ║
║  1. WebSocket CVD — real tick-based (most accurate)          ║
║  2. Stock Scoring System (0-100) — top score only            ║
║  3. 15-min trend confirm (multi-timeframe)                   ║
║  4. 5-min EMA5 pullback + slope (45° angle)                  ║
║  5. Volume surge (1.5x avg)                                  ║
║  6. OI confirmation (Fyers option chain)                     ║
║  7. Nifty regime filter                                      ║
║  8. Session time filter (Prime / Extended / Dead zone)       ║
║  9. Sell side extra strict (OI=2, time 9:30-11:15 only)      ║
╚══════════════════════════════════════════════════════════════╝
"""

from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
import pandas as pd
import numpy as np
import datetime
import threading
import time
import requests
import re
import argparse
import sys
import os
from collections import deque

# ── CLI ──────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Fyers Redirect URL")
args = parser.parse_args()

# ============================================================
#  CREDENTIALS
# ============================================================
APP_ID           = "ESUCFMYU9Q-100"
SECRET_ID        = "1ESVP5WA71"
REDIRECT_URL     = "https://www.google.com/"
TELEGRAM_TOKEN   = "8474252007:AAF-BiJGtj8URcEsd9RMUJkDMfJgKoEN_gw"
TELEGRAM_CHAT_ID = "1250330319"

# ============================================================
#  STRATEGY PARAMETERS
# ============================================================
# ── Core filters ──
CHANGE_THRESHOLD  = 1.2    # min day move % for signal
BODY_RATIO_MIN    = 0.5    # candle body / range ratio
LOOKBACK          = 15     # candles for fresh high/low
NIFTY_LIMIT       = 0.15   # nifty move filter threshold
MAX_SIGNALS       = 3      # max alerts per stock per day

# ── SL / TP ──
ATR_SL_MULT       = 1.5    # SL  = price ± ATR × 1.5
ATR_TP_MULT       = 3.0    # TP  = price ± ATR × 3.0  → 1:2 RR
ATR_SPIKE_MULT    = 2.0    # candle > ATR×2 = spike, skip

# ── EMA pullback ──
EMA_LEN           = 5
PULLBACK_BUFFER   = 0.25

# ── Slope (45° angle) ──
SLOPE_PERIOD      = 6
SLOPE_MIN         = 0.06
SLOPE_MAX         = 0.40

# ── Volume ──
VOL_AVG_PERIOD    = 20
VOL_SURGE_MULT    = 1.5    # raised from 1.4 → 1.5 for better quality

# ── Session windows ──
PRIME_END_H, PRIME_END_M      = 11, 30   # Prime   9:30 – 11:30
EXTENDED_END_H, EXTENDED_END_M = 12, 30  # Extended 11:30 – 12:30
EXTENDED_THRESHOLD = 1.8                  # stricter threshold after 11:30
EXTENDED_SLOPE_MIN = 0.12

# ── OI ──
OI_STRIKE_COUNT     = 5
OI_MIN_SCORE_BUY    = 2    # out of 3
OI_MIN_SCORE_SELL   = 2    # strict — same as buy

# ── Stock Scoring ──
MIN_SCORE_TO_ALERT  = 70   # out of 100 — only best stocks alert

# ── WebSocket CVD ──
CVD_TICK_WINDOW     = 200  # last N ticks per stock for CVD
CVD_SLOPE_BULL      =  0.3 # normalized slope threshold for BUY
CVD_SLOPE_BEAR      = -0.3 # normalized slope threshold for SELL

# ── 15-min multi-timeframe ──
MTF_EMA_LEN         = 9    # 15-min EMA length for trend confirm

# ============================================================
#  GLOBAL STATE
# ============================================================
notified_stocks  = {}
ws_cvd_store     = {}      # {symbol: deque of (price, volume, direction)}
ws_cvd_lock      = threading.Lock()
ws_connected     = threading.Event()

# ============================================================
#  INDICATORS
# ============================================================
def get_ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def get_atr(df, length=14):
    hl  = df['high'] - df['low']
    hc  = (df['high'] - df['close'].shift()).abs()
    lc  = (df['low']  - df['close'].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def get_slope_pct(series, period=6):
    y = series.iloc[-period:].values.astype(float)
    x = np.arange(period)
    if len(y) < period or y[0] == 0:
        return 0.0
    slope, _ = np.polyfit(x, y, 1)
    return (slope / y[0]) * 100

def get_ohlcv_cvd(df, period=8):
    """Fallback OHLCV CVD when WebSocket not yet warm."""
    delta = df.apply(
        lambda r: r['volume'] if r['close'] >= r['open'] else -r['volume'], axis=1
    )
    cvd = delta.cumsum()
    recent = cvd.iloc[-period:].values.astype(float)
    if len(recent) < period:
        return 0.0
    slope, _ = np.polyfit(np.arange(period), recent, 1)
    avg_vol = df['volume'].iloc[-period:].mean()
    return (slope / avg_vol * 100) if avg_vol > 0 else 0.0

# ============================================================
#  WEBSOCKET CVD — Real tick-based
# ============================================================
def ws_on_message(msg):
    """
    Fyers WebSocket tick message handler.
    Each tick has: symbol, ltp, vol (traded qty this tick).
    We infer direction from price movement vs prev tick.
    CVD += vol if price up, -= vol if price down.
    """
    try:
        if not isinstance(msg, dict):
            return
        sym  = msg.get('symbol', '')
        ltp  = msg.get('ltp', 0)
        vol  = msg.get('vol', 0) or msg.get('volume', 0)

        if not sym or ltp == 0:
            return

        with ws_cvd_lock:
            if sym not in ws_cvd_store:
                ws_cvd_store[sym] = deque(maxlen=CVD_TICK_WINDOW)

            q = ws_cvd_store[sym]
            if len(q) > 0:
                prev_ltp = q[-1][0]
                direction = 1 if ltp >= prev_ltp else -1
            else:
                direction = 1

            q.append((ltp, vol, direction))
    except Exception as e:
        pass

def ws_on_connect(msg):
    print("✅ WebSocket connected")
    ws_connected.set()

def ws_on_error(msg):
    print(f"⚠ WebSocket error: {msg}")

def ws_on_close(msg):
    print(f"WebSocket closed: {msg}")
    ws_connected.clear()

def get_ws_cvd_slope(symbol):
    """
    Calculate CVD slope from WebSocket tick deque.
    Returns normalized slope — positive = buying pressure, negative = selling.
    Returns None if not enough ticks yet (fallback to OHLCV).
    """
    with ws_cvd_lock:
        q = ws_cvd_store.get(symbol)
        if not q or len(q) < 20:
            return None   # not enough data yet

        ticks = list(q)

    # Build cumulative delta from ticks
    cvd = []
    running = 0
    for ltp, vol, direction in ticks:
        running += vol * direction
        cvd.append(running)

    cvd = np.array(cvd, dtype=float)

    # Slope of last 20 ticks
    n   = min(20, len(cvd))
    y   = cvd[-n:]
    x   = np.arange(n)
    slope, _ = np.polyfit(x, y, 1)

    # Normalize by avg volume
    avg_vol = np.mean([t[1] for t in ticks[-n:]]) or 1
    return slope / avg_vol

# ============================================================
#  MULTI-TIMEFRAME (15-min trend)
# ============================================================
def get_15min_trend(fyers_client, symbol, today, start_date, today_str):
    """
    15-min chart trend confirm.
    Returns: 'BULL', 'BEAR', or 'NEUTRAL'
    """
    try:
        r = fyers_client.history({
            "symbol": symbol, "resolution": "15",
            "date_format": "1", "range_from": start_date, "range_to": today_str
        })
        if r['s'] != 'ok':
            return 'NEUTRAL'

        df15 = pd.DataFrame(r['candles'], columns=['time','open','high','low','close','volume'])
        df15_t = df15[pd.to_datetime(df15['time'], unit='s').dt.date == today]

        if len(df15_t) < 3:
            return 'NEUTRAL'

        df15_t = df15_t.copy()
        df15_t['ema9'] = get_ema(df15_t['close'], MTF_EMA_LEN)

        last = df15_t.iloc[-1]
        prev = df15_t.iloc[-2]

        # Bull: price above EMA9, EMA9 rising, last candle green
        if (last['close'] > last['ema9']
                and last['ema9'] > prev['ema9']
                and last['close'] > last['open']):
            return 'BULL'

        # Bear: price below EMA9, EMA9 falling, last candle red
        if (last['close'] < last['ema9']
                and last['ema9'] < prev['ema9']
                and last['close'] < last['open']):
            return 'BEAR'

        return 'NEUTRAL'
    except:
        return 'NEUTRAL'

# ============================================================
#  STOCK SCORING (0 – 100)
# ============================================================
def score_stock(s_move, slope, cvd_slope_norm, vol_ratio,
                is_fresh, is_strong, is_not_spike,
                ema_aligned, mtf_trend, signal):
    """
    Score a stock 0-100. Higher = better setup.
    Only stocks >= MIN_SCORE_TO_ALERT get alerted.

    Breakdown:
      Day move strength      : 20 pts
      Slope quality          : 15 pts
      CVD strength           : 20 pts
      Volume surge           : 15 pts
      Fresh high/low         : 10 pts
      Strong candle body     : 10 pts
      MTF trend alignment    : 10 pts
    """
    score = 0
    breakdown = {}

    # Day move (20 pts)
    move_abs = abs(s_move)
    if   move_abs >= 3.5: pts = 20
    elif move_abs >= 2.5: pts = 16
    elif move_abs >= 1.8: pts = 12
    elif move_abs >= 1.2: pts = 8
    else:                 pts = 4
    score += pts; breakdown['move'] = pts

    # Slope quality (15 pts)
    slope_abs = abs(slope)
    if   0.15 <= slope_abs <= 0.30: pts = 15   # perfect 45°
    elif 0.10 <= slope_abs <= 0.35: pts = 10
    elif 0.06 <= slope_abs <= 0.40: pts = 6
    else:                           pts = 0
    score += pts; breakdown['slope'] = pts

    # CVD strength (20 pts)
    if cvd_slope_norm is not None:
        cvd_abs = abs(cvd_slope_norm)
        if   cvd_abs >= 2.0: pts = 20
        elif cvd_abs >= 1.0: pts = 15
        elif cvd_abs >= 0.5: pts = 10
        elif cvd_abs >= 0.3: pts = 6
        else:                pts = 2
    else:
        pts = 8   # OHLCV fallback — partial credit
    score += pts; breakdown['cvd'] = pts

    # Volume surge (15 pts)
    if   vol_ratio >= 3.0: pts = 15
    elif vol_ratio >= 2.0: pts = 12
    elif vol_ratio >= 1.5: pts = 8
    elif vol_ratio >= 1.2: pts = 4
    else:                  pts = 0
    score += pts; breakdown['volume'] = pts

    # Fresh high/low (10 pts)
    pts = 10 if is_fresh else 0
    score += pts; breakdown['fresh'] = pts

    # Strong candle (10 pts)
    pts = 10 if (is_strong and is_not_spike) else (5 if is_strong else 0)
    score += pts; breakdown['candle'] = pts

    # MTF trend (10 pts)
    if signal == 'BUY'  and mtf_trend == 'BULL': pts = 10
    elif signal == 'SELL' and mtf_trend == 'BEAR': pts = 10
    elif mtf_trend == 'NEUTRAL':                   pts = 5
    else:                                          pts = 0
    score += pts; breakdown['mtf'] = pts

    return min(score, 100), breakdown

# ============================================================
#  OI CONFIRMATION
# ============================================================
def get_oi_confirmation(fyers_client, raw_symbol, signal_side):
    try:
        stock = raw_symbol.replace("NSE:", "").replace("-EQ", "")
        resp  = fyers_client.optionchain({
            "symbol": f"NSE:{stock}-EQ",
            "strikecount": OI_STRIKE_COUNT,
            "timestamp": ""
        })

        if resp.get('s') != 'ok':
            return False, "OI N/A", 0

        full_chain = resp['data']['optionsChain']
        chain = [x for x in full_chain if x.get('option_type') in ('CE','PE')]
        if not chain:
            return False, "OI empty", 0

        ltp_entry  = next((x for x in full_chain if x.get('option_type') == ''), None)
        ltp        = ltp_entry.get('ltp', 0) if ltp_entry else 0
        strikes    = sorted(set(x['strike_price'] for x in chain))
        atm_strike = min(strikes, key=lambda x: abs(x - ltp)) if ltp else strikes[len(strikes)//2]

        atm_idx   = strikes.index(atm_strike)
        atm_range = set(strikes[max(0, atm_idx-2): atm_idx+3])
        atm_slice = [x for x in chain if x['strike_price'] in atm_range]

        ce_oi_chg = sum(x.get('oich', 0) or 0 for x in atm_slice if x['option_type'] == 'CE')
        pe_oi_chg = sum(x.get('oich', 0) or 0 for x in atm_slice if x['option_type'] == 'PE')

        score  = 0
        detail = []

        if signal_side == "BUY":
            if ce_oi_chg > 0:                          score += 1; detail.append("CE OI↑")
            if pe_oi_chg < 0:                          score += 1; detail.append("PE OI↓")
            if ce_oi_chg > abs(pe_oi_chg) * 0.5:      score += 1; detail.append("CE dom")
            confirmed = score >= OI_MIN_SCORE_BUY
        else:
            if pe_oi_chg > 0:                          score += 1; detail.append("PE OI↑")
            if ce_oi_chg < 0:                          score += 1; detail.append("CE OI↓")
            if pe_oi_chg > abs(ce_oi_chg) * 0.5:      score += 1; detail.append("PE dom")
            confirmed = score >= OI_MIN_SCORE_SELL

        msg = f"OI {score}✓ ({', '.join(detail)})" if detail else f"OI {score}✓"
        return confirmed, msg, score

    except Exception as e:
        print(f"  OI error [{raw_symbol}]: {e}")
        return False, "OI err", 0

# ============================================================
#  SLOW ACCUMULATION
# ============================================================
def is_slow_accumulation(df_today):
    now = datetime.datetime.now()
    if now.hour > 10 or (now.hour == 10 and now.minute >= 30):
        return True

    if len(df_today) < 3:
        return False

    m_open  = df_today.iloc[0]['open']
    c_price = df_today.iloc[-1]['close']
    move    = ((c_price - m_open) / m_open * 100) if m_open != 0 else 0

    ranges  = df_today['high'] - df_today['low']
    bodies  = (df_today['close'] - df_today['open']).abs()
    avg_br  = (bodies / ranges.replace(0, np.nan)).mean()

    return (0.8 <= move <= 2.5) and (avg_br >= 0.40)

# ============================================================
#  AUTH & TELEGRAM
# ============================================================
def get_access_token():
    if not args.url:
        return None
    try:
        match = re.search(r'auth_code=([^&]+)', args.url)
        if match:
            session = fyersModel.SessionModel(
                client_id=APP_ID, secret_key=SECRET_ID,
                redirect_uri=REDIRECT_URL,
                response_type="code", grant_type="authorization_code"
            )
            session.set_token(match.group(1))
            return session.generate_token().get("access_token")
    except Exception as e:
        print(f"Login Error: {e}")
    return None

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5
        )
    except Exception as e:
        print(f"Telegram error: {e}")

# ============================================================
#  OPTION STRIKE SELECTOR
# ============================================================
def get_perfect_strike(symbol, price, side):
    if   "BANKNIFTY" in symbol: step = 100
    elif "NIFTY"     in symbol: step = 50
    elif price > 1000:          step = 10
    elif price > 500:           step = 5
    else:                       step = 2.5
    atm = round(price / step) * step
    return f"{int(atm + step)} CE" if side == "BUY" else f"{int(atm - step)} PE"

# ============================================================
#  DAILY RESET
# ============================================================
def maybe_reset_daily():
    now = datetime.datetime.now()
    if now.hour == 9 and 15 <= now.minute <= 16:
        if notified_stocks:
            notified_stocks.clear()
            print("✅ Daily reset done")

# ============================================================
#  LOGIN
# ============================================================
token = get_access_token()
if not token:
    sys.exit("🔴 Login Failed.")

fyers = fyersModel.FyersModel(client_id=APP_ID, token=token, is_async=False)
print("✅ Fyers connected")

# ============================================================
#  STOCK UNIVERSE
# ============================================================
stocks_list = (
    "360ONE,ABB,ABCAPITAL,ADANIENSOL,ADANIENT,ADANIGREEN,ADANIPORTS,ALKEM,AMBER,"
    "AMBUJACEM,ANGELONE,APLAPOLLO,APOLLOHOSP,ASHOKLEY,ASIANPAINT,ASTRAL,AUBANK,"
    "AUROPHARMA,AXISBANK,BAJAJ_AUTO,BAJAJFINSV,BAJAJHLDNG,BAJFINANCE,BANDHANBNK,"
    "BANKBARODA,BANKINDIA,BDL,BEL,BHARATFORG,BHARTIARTL,BHEL,BIOCON,BLUESTARCO,"
    "BOSCHLTD,BPCL,BRITANNIA,BSE,CAMS,CANBK,CDSL,CGPOWER,CHOLAFIN,CIPLA,COALINDIA,"
    "COFORGE,COLPAL,CONCOR,CROMPTON,CUMMINSIND,DABUR,DALBHARAT,DELHIVERY,DIVISLAB,"
    "DIXON,DLF,DMART,DRREDDY,EICHERMOT,ETERNAL,EXIDEIND,FEDERALBNK,FORTIS,GAIL,"
    "GLENMARK,GMRAIRPORT,GODREJCP,GODREJPROP,GRASIM,HAL,HAVELLS,HCLTECH,HDFCAMC,"
    "HDFCBANK,HDFCLIFE,HEROMOTOCO,HINDALCO,HINDPETRO,HINDUNILVR,HINDZINC,HUDCO,"
    "ICICIBANK,ICICIGI,ICICIPRULI,IDEA,IDFCFIRSTB,IEX,IIFL,INDHOTEL,INDIANB,"
    "INDIGO,INDUSINDBK,INDUSTOWER,INFY,INOXWIND,IOC,IRCTC,IREDA,IRFC,ITC,"
    "JINDALSTEL,JIOFIN,JSWENERGY,JSWSTEEL,JUBLFOOD,KALYANKJIL,KAYNES,KEI,KFINTECH,"
    "KOTAKBANK,KPITTECH,LAURUSLABS,LICHSGFIN,LICI,LODHA,LT,LTF,LTIM,LUPIN,M_M,"
    "MANAPPURAM,MANKIND,MARICO,MARUTI,MAXHEALTH,MAZDOCK,MCX,MFSL,MOTHERSON,"
    "MPHASIS,MUTHOOTFIN,NATIONALUM,NAUKRI,NBCC,NESTLEIND,NHPC,NMDC,NTPC,NUVAMA,"
    "NYKAA,OBEROIRLTY,OFSS,OIL,ONGC,PAGEIND,PATANJALI,PAYTM,PERSISTENT,PETRONET,"
    "PFC,PGEL,PHOENIXLTD,PIDILITIND,PIIND,PNB,PNBHOUSING,POLICYBZR,POLYCAB,"
    "POWERGRID,POWERINDIA,PPLPHARMA,PREMIERENE,PRESTIGE,RBLBANK,RECLTD,RELIANCE,"
    "RVNL,SAIL,SAMMAANCAP,SBICARD,SBILIFE,SBIN,SHREECEM,SHRIRAMFIN,SIEMENS,"
    "SOLARINDS,SONACOMS,SRF,SUNPHARMA,SUPREMEIND,SUZLON,SWIGGY,SYNGENE,TATACONSUM,"
    "TATAELXSI,TATAPOWER,TATASTEEL,TATATECH,TCS,TECHM,TIINDIA,TITAN,TMPV,"
    "TORNTPHARM,TORNTPOWER,TRENT,TVSMOTOR,ULTRACEMCO,UNIONBANK,UNITDSPR,UNOMINDA,"
    "UPL,VBL,VEDL,VOLTAS,WAAREEENER,WIPRO,YESBANK,ZYDUSLIFE"
)
stocks = [s.strip() for s in stocks_list.split(",")]

# ============================================================
#  WEBSOCKET SETUP — subscribe all stocks for live CVD
# ============================================================
def start_websocket():
    try:
        ws_symbols = [f"NSE:{s}-EQ" for s in stocks]

        fws = data_ws.FyersDataSocket(
            access_token  = f"{APP_ID}:{token}",
            write_to_file = False,
            litemode      = True,    # litemode = LTP + volume only (faster)
            reconnect     = True,
            on_message    = ws_on_message,
            on_error      = ws_on_error,
            on_connect    = ws_on_connect,
            on_close      = ws_on_close,
        )

        # Subscribe in chunks of 200 (API limit per call)
        def run():
            fws.connect()
            # Wait for connection
            ws_connected.wait(timeout=15)
            if ws_connected.is_set():
                for i in range(0, len(ws_symbols), 200):
                    chunk = ws_symbols[i:i+200]
                    fws.subscribe(symbols=chunk, data_type="SymbolUpdate")
                    time.sleep(0.5)
                print(f"✅ WebSocket subscribed to {len(ws_symbols)} stocks")
            else:
                print("⚠ WebSocket connection timeout — using OHLCV CVD fallback")

        t = threading.Thread(target=run, daemon=True)
        t.start()
        return True
    except Exception as e:
        print(f"⚠ WebSocket start failed: {e} — using OHLCV CVD")
        return False

# ============================================================
#  MAIN SCAN
# ============================================================
def scan():
    maybe_reset_daily()
    now   = datetime.datetime.now()
    today = datetime.date.today()

    # Skip opening noise
    if now.hour == 9 and now.minute < 30:
        print("⏳ Waiting for 9:30 AM...")
        return

    # Session classification
    is_prime    = (now.hour < PRIME_END_H) or (now.hour == PRIME_END_H and now.minute < PRIME_END_M)
    is_extended = not is_prime and (
        (now.hour < EXTENDED_END_H) or (now.hour == EXTENDED_END_H and now.minute < EXTENDED_END_M)
    )
    is_dead = not is_prime and not is_extended

    if is_dead:
        print("⛔ Dead zone (after 12:30 PM) — no new entries")
        return

    # Sell only in first half of prime session
    sell_allowed_time = now.hour < 11 or (now.hour == 11 and now.minute < 15)

    session_tag   = "🟢 Prime" if is_prime else "🟡 Extended"
    thr           = CHANGE_THRESHOLD if is_prime else EXTENDED_THRESHOLD
    slp_min       = SLOPE_MIN        if is_prime else EXTENDED_SLOPE_MIN

    start_date = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    today_str  = today.strftime('%Y-%m-%d')

    # Nifty regime
    try:
        n_res = fyers.history({
            "symbol": "NSE:NIFTY50-INDEX", "resolution": "5",
            "date_format": "1", "range_from": start_date, "range_to": today_str
        })
        if n_res['s'] != 'ok':
            print("Nifty data failed"); return

        df_n  = pd.DataFrame(n_res['candles'], columns=['time','open','high','low','close','volume'])
        df_nt = df_n[pd.to_datetime(df_n['time'], unit='s').dt.date == today]
        if len(df_nt) < 3: return

        n_move = ((df_nt.iloc[-1]['close'] - df_nt.iloc[0]['open']) / df_nt.iloc[0]['open']) * 100
    except Exception as e:
        print(f"Nifty error: {e}"); return

    ws_warm = ws_connected.is_set()
    print(f"\n🔍 {len(stocks)} stocks | Nifty: {n_move:+.2f}% | {session_tag} | WS CVD: {'✅' if ws_warm else '⚠ fallback'} | {now.strftime('%H:%M:%S')}")

    signals_found = 0
    candidates    = []   # collect all passing stocks with scores

    for s in stocks:
        try:
            symbol = f"NSE:{s}-EQ"

            # 5-min data
            h5 = fyers.history({
                "symbol": symbol, "resolution": "5",
                "date_format": "1", "range_from": start_date, "range_to": today_str
            })
            if h5['s'] != 'ok': continue

            df = pd.DataFrame(h5['candles'], columns=['time','open','high','low','close','volume'])
            if len(df) < 30: continue

            df['ema5'] = get_ema(df['close'], EMA_LEN)
            df['atr']  = get_atr(df, 14)

            curr = df.iloc[-2]
            df_t = df[pd.to_datetime(df['time'], unit='s').dt.date == today]
            if len(df_t) < 3: continue

            # Basic calculations
            m_open = df_t.iloc[0]['open']
            s_move = ((curr['close'] - m_open) / m_open * 100) if m_open != 0 else 0

            is_fresh_high = curr['close'] > df.iloc[-(LOOKBACK+2):-2]['high'].max()
            is_fresh_low  = curr['close'] < df.iloc[-(LOOKBACK+2):-2]['low'].min()

            c_rng        = curr['high'] - curr['low']
            is_strong    = c_rng > 0 and (abs(curr['close'] - curr['open']) / c_rng) >= BODY_RATIO_MIN
            is_not_spike = c_rng <= curr['atr'] * ATR_SPIKE_MULT

            slope        = get_slope_pct(df['close'], SLOPE_PERIOD)
            is_45_buy    = slp_min <=  slope <= SLOPE_MAX
            is_45_sell   = slp_min <= -slope <= SLOPE_MAX

            avg_vol      = df['volume'].rolling(VOL_AVG_PERIOD).mean().iloc[-2]
            vol_ratio    = curr['volume'] / avg_vol if avg_vol > 0 else 0
            is_vol_surge = vol_ratio >= VOL_SURGE_MULT

            d_ema_b   = (curr['low']  - curr['ema5']) / curr['ema5'] * 100
            d_ema_s   = (curr['ema5'] - curr['high']) / curr['ema5'] * 100
            is_buy_pb = curr['low'] <= curr['ema5'] or (d_ema_b <= PULLBACK_BUFFER and curr['low'] > curr['ema5'])
            is_sell_pb= curr['high'] >= curr['ema5'] or (d_ema_s <= PULLBACK_BUFFER and curr['high'] < curr['ema5'])

            r_buy  = not (n_move < -NIFTY_LIMIT and s_move < n_move * 0.4)
            w_sell = not (n_move >  NIFTY_LIMIT and s_move > n_move * 0.4)

            accum_ok = is_slow_accumulation(df_t)

            # CVD — WebSocket if warm, else OHLCV fallback
            ws_cvd_norm = get_ws_cvd_slope(symbol)
            if ws_cvd_norm is not None:
                cvd_slope_norm = ws_cvd_norm
                cvd_rising     = cvd_slope_norm >= CVD_SLOPE_BULL
                cvd_falling    = cvd_slope_norm <= CVD_SLOPE_BEAR
                is_fake_rally  = s_move > 0 and cvd_slope_norm < -0.5
                is_fake_drop   = s_move < 0 and cvd_slope_norm >  0.5
            else:
                # OHLCV fallback
                ohlcv_cvd      = get_ohlcv_cvd(df, period=8)
                cvd_slope_norm = ohlcv_cvd
                cvd_rising     = ohlcv_cvd >  0.5
                cvd_falling    = ohlcv_cvd < -0.5
                is_fake_rally  = s_move > 0 and ohlcv_cvd < -1.0
                is_fake_drop   = s_move < 0 and ohlcv_cvd >  1.0

            # SL / TP
            atr_val = curr['atr']
            buy_sl  = round(curr['close'] - atr_val * ATR_SL_MULT, 2)
            buy_tp  = round(curr['close'] + atr_val * ATR_TP_MULT, 2)
            sell_sl = round(curr['close'] + atr_val * ATR_SL_MULT, 2)
            sell_tp = round(curr['close'] - atr_val * ATR_TP_MULT, 2)

            if s not in notified_stocks:
                notified_stocks[s] = {'b': 0, 's': 0, 'last': 0}

            # ── SIGNAL DECISION ──
            signal = None

            buy_ok = (
                s_move >= thr
                and is_fresh_high
                and is_strong
                and is_not_spike
                and r_buy
                and is_buy_pb
                and curr['close'] > curr['ema5']
                and is_vol_surge
                and is_45_buy
                and accum_ok
                and cvd_rising
                and not is_fake_rally
                and notified_stocks[s]['b'] < MAX_SIGNALS
            )

            sell_ok = (
                s_move <= -thr
                and is_fresh_low
                and is_strong
                and is_not_spike
                and w_sell
                and is_sell_pb
                and curr['close'] < curr['ema5']
                and is_vol_surge
                and is_45_sell
                and accum_ok
                and cvd_falling
                and not is_fake_drop
                and sell_allowed_time       # sell only before 11:15 AM
                and notified_stocks[s]['s'] < MAX_SIGNALS
            )

            if buy_ok:   signal = "BUY"
            elif sell_ok: signal = "SELL"

            if not signal: continue
            if curr['time'] <= notified_stocks[s]['last'] + 300: continue

            # Multi-timeframe confirm
            mtf = get_15min_trend(fyers, symbol, today, start_date, today_str)
            if signal == 'BUY'  and mtf == 'BEAR': continue   # 15-min against us
            if signal == 'SELL' and mtf == 'BULL': continue

            # Stock Score
            score, breakdown = score_stock(
                s_move, slope, cvd_slope_norm, vol_ratio,
                is_fresh_high if signal=='BUY' else is_fresh_low,
                is_strong, is_not_spike,
                curr['close'] > curr['ema5'],
                mtf, signal
            )

            if score < MIN_SCORE_TO_ALERT:
                print(f"  ⬇ {s} {signal} score {score}/100 — below threshold, skip")
                continue

            # Collect candidate
            candidates.append({
                's': s, 'symbol': symbol, 'signal': signal,
                'score': score, 'breakdown': breakdown,
                'curr': curr, 's_move': s_move, 'slope': slope,
                'cvd_slope_norm': cvd_slope_norm, 'vol_ratio': vol_ratio,
                'mtf': mtf, 'buy_sl': buy_sl, 'buy_tp': buy_tp,
                'sell_sl': sell_sl, 'sell_tp': sell_tp,
                'avg_vol': avg_vol, 'session_tag': session_tag,
                'ws_cvd': ws_cvd_norm is not None
            })

            time.sleep(0.05)

        except Exception as e:
            print(f"  ⚠ [{s}]: {e}")
            continue

    # ── SORT BY SCORE — send top signals only ──
    candidates.sort(key=lambda x: x['score'], reverse=True)

    for c in candidates:
        s = c['s']

        # OI confirmation — only for top candidates
        oi_confirmed, oi_msg, oi_score = get_oi_confirmation(fyers, c['symbol'], c['signal'])

        if not oi_confirmed:
            print(f"  ⚡ {s} {c['signal']} score={c['score']} — OI not confirmed, skip")
            continue

        notified_stocks[s]['last'] = int(c['curr']['time'])
        sl = c['buy_sl']  if c['signal'] == 'BUY' else c['sell_sl']
        tp = c['buy_tp']  if c['signal'] == 'BUY' else c['sell_tp']
        rr = round(abs(tp - c['curr']['close']) / max(abs(sl - c['curr']['close']), 0.01), 1)

        if c['signal'] == 'BUY':  notified_stocks[s]['b'] += 1
        else:                      notified_stocks[s]['s'] += 1

        perfect_option = get_perfect_strike(s, c['curr']['close'], c['signal'])
        cvd_src = "WS" if c['ws_cvd'] else "OHLCV"
        emoji   = "🚀" if c['signal'] == 'BUY' else "📉"

        bd = c['breakdown']
        msg = (
            f"{emoji} 🔥 *STRONG {c['signal']}*: `{s}` {c['session_tag']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⭐ Score  : *{c['score']}/100*\n"
            f"💰 Price  : ₹{c['curr']['close']}\n"
            f"📊 Move   : {c['s_move']:+.2f}%\n"
            f"📐 Slope  : {c['slope']:+.3f}%/candle\n"
            f"📦 Volume : {c['vol_ratio']:.1f}x avg\n"
            f"🌊 CVD    : {c['cvd_slope_norm']:+.2f} [{cvd_src}]\n"
            f"📈 15-min : {c['mtf']}\n"
            f"🔄 OI     : {oi_msg}\n"
            f"🎯 Option : `{perfect_option}`\n"
            f"🛡 SL     : ₹{sl}  |  🎯 TP: ₹{tp}\n"
            f"⚖️ RR     : 1:{rr}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📋 _Move:{bd['move']} Slope:{bd['slope']} CVD:{bd['cvd']} Vol:{bd['volume']} Fresh:{bd['fresh']} Candle:{bd['candle']} MTF:{bd['mtf']}_"
        )
        send_telegram(msg)
        print(f"  ✅ ALERT: {s} {c['signal']} | Score:{c['score']} | OI:{oi_msg} | CVD:{c['cvd_slope_norm']:+.2f} | MTF:{c['mtf']}")
        signals_found += 1

    print(f"  → Done. {len(candidates)} candidates, {signals_found} alerts sent.")

# ============================================================
#  MAIN
# ============================================================
print("=" * 55)
print("  TRADING BOT v3 — WebSocket CVD + Scoring System")
print("=" * 55)

send_telegram(
    "🚀 *Bot v3 Online*\n"
    "WebSocket CVD + Stock Scoring + Multi-timeframe\n"
    "Sirf 70+ score + OI confirmed signals aayenge"
)

# Start WebSocket in background
ws_started = start_websocket()
print("⏳ Warming up WebSocket CVD (30 sec)...")
time.sleep(10)   # let WebSocket collect some ticks before first scan

while True:
    now = datetime.datetime.now()

    if now.hour == 15 and now.minute >= 30:
        send_telegram("🔴 *Bot v3 Offline* — Market closed")
        print("Market closed. Stopping.")
        break

    if now.minute % 5 == 0 and 4 <= now.second <= 8:
        scan()
        time.sleep(15)

    time.sleep(1)
