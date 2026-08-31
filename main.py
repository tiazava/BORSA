import os
import math
import time
import datetime as dt
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from io import StringIO
import re

import requests
import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# CONFIGURAZIONE
# ============================================================
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

LOOKAHEAD_DAYS = int(os.getenv("LOOKAHEAD_DAYS", "30"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "75"))        # 75 = 4 stelle
TOP_N = int(os.getenv("TOP_N", "5"))
NEWS_LOOKBACK_DAYS = int(os.getenv("NEWS_LOOKBACK_DAYS", "14"))
REQUEST_SLEEP = float(os.getenv("REQUEST_SLEEP", "0.15"))

# Limiti di sicurezza dello scoring
MIN_HISTORY_ROWS = 120


# ============================================================
# UNIVERSO TITOLI
# ============================================================
FTSE_MIB = [
    "A2A.MI", "AMP.MI", "ARISTON.MI", "AZM.MI", "BAMI.MI", "BCA.MI",
    "BPE.MI", "BZZ.MI", "CPR.MI", "DIA.MI", "ENEL.MI", "ENI.MI", "ERG.MI",
    "RACE.MI", "FBK.MI", "G.MI", "HER.MI", "INW.MI", "ISP.MI", "LDO.MI",
    "MB.MI", "MONC.MI", "NEXI.MI", "PIR.MI", "PNT.MI", "PRY.MI", "REC.MI",
    "RWAY.MI", "SRG.MI", "STLAM.MI", "STMMI.MI", "TIT.MI", "TEN.MI",
    "TRN.MI", "UCG.MI", "US.MI"
]

DOW_JONES = [
    "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX",
    "DIS", "DOW", "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD",
    "MMM", "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WMT"
]

NASDAQ_100 = [
    "ADBE", "AMD", "ABNB", "ALNY", "AMAT", "APP", "ARM", "ASML", "AVGO",
    "AXON", "BKNG", "CDNS", "CEG", "CHTR", "CMCSA", "COST", "CRWD", "CSCO",
    "CTAS", "CSX", "DASH", "DDOG", "DXCM", "EA", "EXC", "FANG", "FAST",
    "FTNT", "GEHC", "GILD", "GOOG", "GOOGL", "HON", "IDXX", "INTC", "INTU",
    "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "MAR", "MCHP", "MDLZ",
    "MELI", "META", "MNST", "MRVL", "MSFT", "MU", "NFLX", "NVDA", "ODFL",
    "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD", "PEP", "PLTR", "PYPL",
    "QCOM", "REGN", "ROP", "ROST", "SBUX", "SHOP", "SNPS", "TMUS", "TSLA",
    "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "WDC", "XEL"
]

# Mercati base sempre disponibili. Gli altri indici vengono caricati
# dinamicamente da tabelle pubbliche; se un indice non è raggiungibile,
# gli altri continuano comunque a essere analizzati.
BASE_MARKETS: Dict[str, List[str]] = {
    "🇮🇹 FTSE MIB": FTSE_MIB,
    "🇺🇸 DOW JONES": DOW_JONES,
    "🇺🇸 NASDAQ-100": NASDAQ_100,
}

INDEX_SOURCES = {
    "🇩🇪 DAX 40": {
        "url": "https://en.wikipedia.org/wiki/DAX",
        "columns": ["Ticker symbol", "Ticker", "Symbol"],
        "suffix": ".DE",
    },
    "🇫🇷 CAC 40": {
        "url": "https://en.wikipedia.org/wiki/CAC_40",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".PA",
    },
    "🇬🇧 FTSE 100": {
        "url": "https://en.wikipedia.org/wiki/FTSE_100_Index",
        "columns": ["EPIC", "Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".L",
    },
    "🇳🇱 AEX": {
        "url": "https://en.wikipedia.org/wiki/AEX_index",
        "columns": ["Ticker symbol", "Ticker", "Symbol"],
        "suffix": ".AS",
    },
    "🇨🇭 SMI": {
        "url": "https://en.wikipedia.org/wiki/Swiss_Market_Index",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".SW",
    },
    "🇨🇦 TSX 60": {
        "url": "https://en.wikipedia.org/wiki/S%26P/TSX_60",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".TO",
    },
    "🇯🇵 Nikkei 225": {
        "url": "https://en.wikipedia.org/wiki/Nikkei_225",
        "columns": ["Code", "Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".T",
    },
    # Mercati secondari: mid-cap USA + Europa/Asia selezionata.
    "🇺🇸 S&P MidCap 400": {
        "url": "https://en.wikipedia.org/wiki/S%26P_400",
        "columns": ["Symbol", "Ticker", "Ticker symbol"],
        "suffix": "",
    },
    "🇪🇸 IBEX 35": {
        "url": "https://en.wikipedia.org/wiki/IBEX_35",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".MC",
    },
    "🇸🇪 OMX Stockholm 30": {
        "url": "https://en.wikipedia.org/wiki/OMX_Stockholm_30",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".ST",
    },
    "🇭🇰 Hang Seng": {
        "url": "https://en.wikipedia.org/wiki/Hang_Seng_Index",
        "columns": ["Ticker", "Code", "Ticker symbol", "Symbol"],
        "suffix": ".HK",
    },
    "🇸🇬 Straits Times": {
        "url": "https://en.wikipedia.org/wiki/Straits_Times_Index",
        "columns": ["Ticker", "Stock symbol", "Symbol"],
        "suffix": ".SI",
    },
    "🇧🇪 BEL 20": {
        "url": "https://en.wikipedia.org/wiki/BEL_20",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".BR",
    },
    "🇦🇹 ATX": {
        "url": "https://en.wikipedia.org/wiki/Austrian_Traded_Index",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".VI",
    },
    "🇵🇹 PSI": {
        "url": "https://en.wikipedia.org/wiki/PSI_(Portugal)",
        "columns": ["Ticker", "Ticker symbol", "Symbol"],
        "suffix": ".LS",
    },
}

def _flatten_column(col) -> str:
    if isinstance(col, tuple):
        return " ".join(str(x) for x in col if str(x) != "nan").strip()
    return str(col).strip()

def _normalize_exchange_ticker(raw: str, suffix: str) -> Optional[str]:
    value = str(raw).strip().upper()
    value = re.sub(r"\[[^\]]+\]", "", value).strip()
    if not value or value in {"NAN", "NONE", "N/A", "-"}:
        return None

    # Giappone: codice numerico a 4 cifre.
    if suffix == ".T":
        m = re.search(r"\b(\d{4})\b", value)
        return f"{m.group(1)}.T" if m else None

    # Hong Kong: Yahoo usa normalmente codice numerico a 4 cifre + .HK.
    if suffix == ".HK":
        m = re.search(r"\b(\d{1,5})\b", value.replace(",", ""))
        if m:
            return f"{int(m.group(1)):04d}.HK"
        return None

    known_suffixes = (
        ".DE", ".PA", ".L", ".AS", ".SW", ".TO", ".MC", ".ST",
        ".SI", ".BR", ".VI", ".LS"
    )
    for known in known_suffixes:
        if value.endswith(known):
            value = value[:-len(known)]
            break

    value = value.split()[0].strip()
    # Yahoo usa '-' per molte classi azionarie (es. BRK-B).
    if suffix in {"", ".L", ".TO"}:
        value = value.replace(".", "-")
    value = re.sub(r"[^A-Z0-9\-]", "", value)
    if not value:
        return None
    return value + suffix

def load_index_from_public_table(market: str, cfg: dict) -> List[str]:
    try:
        headers = {"User-Agent": "Mozilla/5.0 MarketOpportunityScanner/3.0"}
        r = requests.get(cfg["url"], headers=headers, timeout=20)
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text))

        for table in tables:
            cols = {_flatten_column(c): c for c in table.columns}
            chosen = None
            for wanted in cfg["columns"]:
                for flat, original in cols.items():
                    if flat.lower() == wanted.lower() or wanted.lower() in flat.lower():
                        chosen = original
                        break
                if chosen is not None:
                    break
            if chosen is None:
                continue

            tickers = []
            for raw in table[chosen].tolist():
                t = _normalize_exchange_ticker(raw, cfg["suffix"])
                if t and t not in tickers:
                    tickers.append(t)

            # Evita di prendere tabelle piccole/non pertinenti.
            if len(tickers) >= 15:
                print(f"{market}: caricati {len(tickers)} componenti")
                return tickers

        print(f"{market}: nessuna tabella componenti riconosciuta")
    except Exception as exc:
        print(f"{market}: errore caricamento componenti: {exc}")
    return []

def build_markets() -> Dict[str, List[str]]:
    markets = dict(BASE_MARKETS)
    for market, cfg in INDEX_SOURCES.items():
        tickers = load_index_from_public_table(market, cfg)
        if tickers:
            markets[market] = tickers
    return markets

MARKETS: Dict[str, List[str]] = {}


# ============================================================
# MODELLI DATI
# ============================================================
@dataclass
class Catalyst:
    kind: str
    date: dt.date
    days_left: int
    confidence: str        # VERIFIED / SINGLE_SOURCE / CONFLICT
    sources: List[str]
    details: str = ""


@dataclass
class AnalysisResult:
    symbol: str
    name: str
    isin: Optional[str]
    market: str
    score: int
    stars: int
    catalyst: Catalyst
    technical_score: int
    analyst_score: int
    estimates_score: int
    catalyst_score: int
    momentum_score: int
    sentiment_score: int
    event_score: int
    fundamental_score: int
    special_catalyst: bool
    event_summary: Optional[str]
    event_source: Optional[str]
    current_price: Optional[float]
    target_price: Optional[float]
    upside_pct: Optional[float]
    reasons: List[str]
    risks: List[str]


# ============================================================
# UTILITY
# ============================================================
def safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        x = float(value)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def first_date(value) -> Optional[dt.date]:
    """Converte vari formati Yahoo/Finnhub in date."""
    if value is None:
        return None

    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()

    if isinstance(value, (list, tuple)) and value:
        for item in value:
            d = first_date(item)
            if d:
                return d

    if isinstance(value, np.ndarray) and len(value):
        for item in value.tolist():
            d = first_date(item)
            if d:
                return d

    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def unique_universe(markets: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """Deduplica ticker identici prima delle chiamate API.
    Se un ticker appartiene a più indici, conserva tutti i nomi dei mercati.
    """
    ticker_markets: Dict[str, List[str]] = {}
    for market, tickers in markets.items():
        for ticker in tickers:
            key = ticker.upper().strip()
            ticker_markets.setdefault(key, [])
            if market not in ticker_markets[key]:
                ticker_markets[key].append(market)
    return [(ticker, " / ".join(ms)) for ticker, ms in ticker_markets.items()]

def is_us_symbol(symbol: str) -> bool:
    # Nel nostro universo i ticker USA sono gli unici senza suffisso exchange.
    return "." not in symbol

def get_isin_safe(stock: yf.Ticker) -> Optional[str]:
    """Recupera ISIN se yfinance lo rende disponibile; mai inventarlo."""
    candidates = []
    try:
        getter = getattr(stock, "get_isin", None)
        if callable(getter):
            candidates.append(getter())
    except Exception:
        pass
    try:
        value = getattr(stock, "isin", None)
        if value:
            candidates.append(value)
    except Exception:
        pass

    for value in candidates:
        if value is None:
            continue
        text = str(value).strip().upper()
        if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", text):
            return text
    return None

def normalize_company_name(name: str) -> str:
    text = re.sub(r"[^A-Z0-9]", "", str(name).upper())
    for suffix in ("PLC", "INC", "CORP", "CORPORATION", "LTD", "LIMITED", "SA", "AG", "NV", "SPA", "CO"):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    return text

def dedupe_company_results(results: List[AnalysisResult]) -> List[AnalysisResult]:
    """Elimina doppie quotazioni della stessa società dal report.
    Priorità: ISIN; fallback: nome normalizzato. Mantiene il risultato migliore.
    """
    ordered = sorted(
        results,
        key=lambda r: (
            r.score,
            1 if r.catalyst.confidence == "VERIFIED" else 0,
            -r.catalyst.days_left,
        ),
        reverse=True,
    )
    seen_isin = set()
    seen_names = set()
    out = []
    for r in ordered:
        isin_key = r.isin if r.isin else None
        name_key = normalize_company_name(r.name)
        if isin_key and isin_key in seen_isin:
            continue
        if name_key and name_key in seen_names:
            continue
        if isin_key:
            seen_isin.add(isin_key)
        if name_key:
            seen_names.add(name_key)
        out.append(r)
    return out


def score_to_stars(score: int) -> int:
    if score >= 85:
        return 5
    if score >= 75:
        return 4
    if score >= 60:
        return 3
    if score >= 40:
        return 2
    return 1


# ============================================================
# FINNHUB - SOLO US SYMBOLS
# IMPORTANTE: MAI rimuovere .MI e interrogare Finnhub come simbolo USA
# ============================================================
def finnhub_get(endpoint: str, params: Optional[dict] = None):
    if not FINNHUB_API_KEY:
        return None

    params = dict(params or {})
    params["token"] = FINNHUB_API_KEY

    try:
        r = requests.get(
            f"https://finnhub.io/api/v1/{endpoint}",
            params=params,
            timeout=15,
        )
        if r.status_code != 200:
            print(f"Finnhub {endpoint}: HTTP {r.status_code}: {r.text[:180]}")
            return None
        return r.json()
    except Exception as exc:
        print(f"Finnhub {endpoint}: {exc}")
        return None


def finnhub_earnings_date_us(symbol: str, today: dt.date, end: dt.date) -> Optional[dt.date]:
    if not is_us_symbol(symbol) or not FINNHUB_API_KEY:
        return None

    data = finnhub_get(
        "calendar/earnings",
        {"from": today.isoformat(), "to": end.isoformat(), "symbol": symbol},
    )
    if not data:
        return None

    events = data.get("earningsCalendar") or []
    dates = []
    for item in events:
        if str(item.get("symbol", "")).upper() != symbol.upper():
            continue
        d = first_date(item.get("date"))
        if d and today <= d <= end:
            dates.append(d)
    return min(dates) if dates else None


def finnhub_recommendation_score_us(symbol: str) -> Tuple[int, List[str]]:
    """0..8 punti extra analyst, solo US."""
    if not is_us_symbol(symbol) or not FINNHUB_API_KEY:
        return 0, []

    data = finnhub_get("stock/recommendation", {"symbol": symbol})
    if not isinstance(data, list) or not data:
        return 0, []

    row = data[0]
    sb = safe_float(row.get("strongBuy")) or 0
    b = safe_float(row.get("buy")) or 0
    h = safe_float(row.get("hold")) or 0
    s = safe_float(row.get("sell")) or 0
    ss = safe_float(row.get("strongSell")) or 0
    total = sb + b + h + s + ss
    if total <= 0:
        return 0, []

    bullish = (sb + b) / total
    bearish = (s + ss) / total

    if bullish >= 0.75 and bearish <= 0.10:
        return 8, [f"🟢 Finnhub analyst consensus molto positivo ({bullish*100:.0f}% Buy/Strong Buy)"]
    if bullish >= 0.60:
        return 5, [f"🟢 Finnhub analyst consensus positivo ({bullish*100:.0f}% Buy/Strong Buy)"]
    if bearish >= 0.25:
        return -3, [f"🔴 Finnhub analyst consensus debole ({bearish*100:.0f}% Sell/Strong Sell)"]
    return 1, ["🟡 Finnhub analyst consensus neutrale/misto"]


# ============================================================
# CATALYST: DATE DA YAHOO + FINNHUB (US)
# ============================================================
def yahoo_earnings_dates(stock: yf.Ticker, today: dt.date, end: dt.date) -> List[dt.date]:
    candidates: List[dt.date] = []

    # 1) calendar per-ticker
    try:
        cal = stock.calendar
        if isinstance(cal, dict):
            for key in ("Earnings Date", "EarningsDate", "earningsDate"):
                if key in cal:
                    value = cal[key]
                    if isinstance(value, (list, tuple, np.ndarray)):
                        for v in value:
                            d = first_date(v)
                            if d:
                                candidates.append(d)
                    else:
                        d = first_date(value)
                        if d:
                            candidates.append(d)
    except Exception:
        pass

    # 2) earnings_dates per-ticker
    try:
        df = stock.get_earnings_dates(limit=12)
        if isinstance(df, pd.DataFrame) and not df.empty:
            for idx in df.index:
                d = first_date(idx)
                if d:
                    candidates.append(d)
    except Exception:
        pass

    valid = sorted({d for d in candidates if today <= d <= end})
    return valid


def yahoo_dividend_date(stock: yf.Ticker, today: dt.date, end: dt.date) -> Optional[dt.date]:
    """Usa ex-dividend date futura se Yahoo la espone nel calendar/info."""
    candidates = []
    try:
        cal = stock.calendar
        if isinstance(cal, dict):
            for key in ("Ex-Dividend Date", "Ex-DividendDate", "exDividendDate"):
                d = first_date(cal.get(key))
                if d:
                    candidates.append(d)
    except Exception:
        pass

    try:
        info = stock.info or {}
        ts = info.get("exDividendDate")
        if ts:
            if isinstance(ts, (int, float)):
                d = dt.datetime.fromtimestamp(ts).date()
            else:
                d = first_date(ts)
            if d:
                candidates.append(d)
    except Exception:
        pass

    valid = sorted({d for d in candidates if today <= d <= end})
    return valid[0] if valid else None


def find_best_catalyst(symbol: str, stock: yf.Ticker) -> Optional[Catalyst]:
    today = dt.date.today()
    end = today + dt.timedelta(days=LOOKAHEAD_DAYS)

    yahoo_dates = yahoo_earnings_dates(stock, today, end)
    yahoo_date = yahoo_dates[0] if yahoo_dates else None
    finnhub_date = finnhub_earnings_date_us(symbol, today, end)

    # Per tutti i mercati non-USA non convertiamo mai il ticker in un simbolo USA.
    if not is_us_symbol(symbol):
        if yahoo_date:
            return Catalyst(
                kind="Trimestrale",
                date=yahoo_date,
                days_left=(yahoo_date - today).days,
                confidence="SINGLE_SOURCE",
                sources=["Yahoo Finance"],
                details="Ticker locale mantenuto con suffisso exchange",
            )
    else:
        if yahoo_date and finnhub_date:
            delta = abs((yahoo_date - finnhub_date).days)
            if delta <= 1:
                chosen = min(yahoo_date, finnhub_date)
                return Catalyst(
                    kind="Trimestrale",
                    date=chosen,
                    days_left=(chosen - today).days,
                    confidence="VERIFIED",
                    sources=["Yahoo Finance", "Finnhub"],
                    details="Le due fonti concordano (±1 giorno)",
                )
            # Data in conflitto: non la consideriamo un catalyst affidabile.
            print(f"{symbol}: CONFLITTO earnings Yahoo={yahoo_date} Finnhub={finnhub_date}")
            return None

        if yahoo_date:
            return Catalyst(
                kind="Trimestrale",
                date=yahoo_date,
                days_left=(yahoo_date - today).days,
                confidence="SINGLE_SOURCE",
                sources=["Yahoo Finance"],
                details="Finnhub non disponibile/non ha restituito una data compatibile",
            )

        if finnhub_date:
            return Catalyst(
                kind="Trimestrale",
                date=finnhub_date,
                days_left=(finnhub_date - today).days,
                confidence="SINGLE_SOURCE",
                sources=["Finnhub"],
                details="Yahoo non ha restituito una data compatibile",
            )

    # Catalyst secondario: ex-dividend. Ha peso inferiore a una trimestrale.
    div_date = yahoo_dividend_date(stock, today, end)
    if div_date:
        return Catalyst(
            kind="Ex-dividend",
            date=div_date,
            days_left=(div_date - today).days,
            confidence="SINGLE_SOURCE",
            sources=["Yahoo Finance"],
            details="Catalyst secondario: data ex-dividend",
        )

    return None


# ============================================================
# INDICATORI TECNICI
# ============================================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()
    df["EMA200"] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI14"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.rolling(14).mean()

    df["VOL20"] = volume.rolling(20).mean()
    df["HIGH20"] = high.rolling(20).max().shift(1)
    df["LOW20"] = low.rolling(20).min().shift(1)

    # momentum
    df["RET20"] = close.pct_change(20)
    df["RET60"] = close.pct_change(60)

    return df


def technical_component(df: pd.DataFrame) -> Tuple[int, List[str], List[str]]:
    """0..25"""
    reasons, risks = [], []
    score = 0
    row = df.iloc[-1]

    close = safe_float(row["Close"])
    ema20 = safe_float(row["EMA20"])
    ema50 = safe_float(row["EMA50"])
    ema200 = safe_float(row["EMA200"])
    rsi = safe_float(row["RSI14"])
    macd = safe_float(row["MACD"])
    macd_sig = safe_float(row["MACD_SIGNAL"])
    high20 = safe_float(row["HIGH20"])

    if close and ema20 and ema50 and ema200:
        if close > ema20 > ema50 > ema200:
            score += 10
            reasons.append("🟢 Trend forte: prezzo > EMA20 > EMA50 > EMA200")
        elif close > ema50 > ema200:
            score += 7
            reasons.append("🟢 Trend rialzista: prezzo sopra EMA50 ed EMA200")
        elif close > ema200:
            score += 4
            reasons.append("🟡 Prezzo sopra EMA200 ma struttura non perfettamente allineata")
        else:
            risks.append("🔴 Prezzo sotto EMA200")

    if rsi is not None:
        if 52 <= rsi <= 68:
            score += 5
            reasons.append(f"🟢 RSI14 favorevole ({rsi:.1f})")
        elif 45 <= rsi < 52 or 68 < rsi <= 75:
            score += 2
            reasons.append(f"🟡 RSI14 neutro/teso ({rsi:.1f})")
        elif rsi > 75:
            risks.append(f"⚠️ RSI14 in ipercomprato ({rsi:.1f})")
        else:
            risks.append(f"🔴 RSI14 debole ({rsi:.1f})")

    if macd is not None and macd_sig is not None:
        if macd > macd_sig and macd > 0:
            score += 5
            reasons.append("🟢 MACD positivo e sopra la signal line")
        elif macd > macd_sig:
            score += 2
            reasons.append("🟡 MACD in miglioramento")
        else:
            risks.append("⚠️ MACD non conferma il momentum")

    if close and high20 and close > high20:
        score += 5
        reasons.append("🔥 Breakout sopra i massimi delle ultime 20 sedute")
    elif close and high20 and close >= high20 * 0.98:
        score += 3
        reasons.append("🟢 Prezzo vicino ai massimi delle ultime 20 sedute")

    return int(clamp(score, 0, 25)), reasons, risks


# ============================================================
# MOMENTUM / VOLUME 0..10
# ============================================================
def momentum_component(df: pd.DataFrame) -> Tuple[int, List[str], List[str]]:
    reasons, risks = [], []
    score = 0
    row = df.iloc[-1]

    ret20 = safe_float(row["RET20"])
    ret60 = safe_float(row["RET60"])
    vol20 = safe_float(row["VOL20"])
    vol = safe_float(row["Volume"])

    if ret20 is not None:
        if ret20 >= 0.08:
            score += 4
            reasons.append(f"🟢 Momentum 1 mese +{ret20*100:.1f}%")
        elif ret20 >= 0.02:
            score += 2
            reasons.append(f"🟢 Momentum 1 mese +{ret20*100:.1f}%")
        elif ret20 < -0.05:
            risks.append(f"🔴 Momentum 1 mese {ret20*100:.1f}%")

    if ret60 is not None:
        if ret60 >= 0.15:
            score += 3
            reasons.append(f"🟢 Momentum 3 mesi +{ret60*100:.1f}%")
        elif ret60 >= 0.04:
            score += 2
            reasons.append(f"🟢 Momentum 3 mesi +{ret60*100:.1f}%")
        elif ret60 < -0.08:
            risks.append(f"🔴 Momentum 3 mesi {ret60*100:.1f}%")

    if vol and vol20 and vol20 > 0:
        ratio = vol / vol20
        if ratio >= 1.5:
            score += 3
            reasons.append(f"🔥 Volume {ratio:.1f}x la media 20 giorni")
        elif ratio >= 1.15:
            score += 2
            reasons.append(f"🟢 Volume sopra media ({ratio:.1f}x)")
        elif ratio < 0.65:
            risks.append("⚠️ Volumi deboli rispetto alla media")

    return int(clamp(score, 0, 10)), reasons, risks


# ============================================================
# ANALYST / TARGET PRICE 0..20
# ============================================================
def analyst_component(stock: yf.Ticker, symbol: str, current_price: float) -> Tuple[int, Optional[float], Optional[float], List[str], List[str]]:
    reasons, risks = [], []
    score = 0
    target = None
    upside = None

    # Target price Yahoo
    try:
        targets = stock.get_analyst_price_targets()
        if isinstance(targets, dict):
            target = safe_float(targets.get("mean") or targets.get("median"))
    except Exception:
        targets = None

    # fallback info
    if target is None:
        try:
            info = stock.info or {}
            target = safe_float(info.get("targetMeanPrice") or info.get("targetMedianPrice"))
        except Exception:
            pass

    if target and current_price > 0:
        upside = (target / current_price - 1.0) * 100.0
        if upside >= 20:
            score += 10
            reasons.append(f"🎯 Target medio analisti: +{upside:.1f}%")
        elif upside >= 12:
            score += 8
            reasons.append(f"🎯 Target medio analisti: +{upside:.1f}%")
        elif upside >= 5:
            score += 5
            reasons.append(f"🟢 Target medio analisti: +{upside:.1f}%")
        elif upside >= 0:
            score += 2
            reasons.append(f"🟡 Target medio analisti poco sopra il prezzo (+{upside:.1f}%)")
        else:
            risks.append(f"🔴 Target medio analisti sotto il prezzo ({upside:.1f}%)")

    # Recommendations Yahoo
    try:
        rec = stock.get_recommendations_summary()
        if isinstance(rec, pd.DataFrame) and not rec.empty:
            row = rec.iloc[0]
            sb = safe_float(row.get("strongBuy")) or 0
            b = safe_float(row.get("buy")) or 0
            h = safe_float(row.get("hold")) or 0
            s = safe_float(row.get("sell")) or 0
            ss = safe_float(row.get("strongSell")) or 0
            total = sb + b + h + s + ss
            if total > 0:
                bullish = (sb + b) / total
                bearish = (s + ss) / total
                if bullish >= 0.75 and bearish <= 0.10:
                    score += 10
                    reasons.append(f"🟢 Yahoo consensus molto positivo ({bullish*100:.0f}% Buy/Strong Buy)")
                elif bullish >= 0.60:
                    score += 7
                    reasons.append(f"🟢 Yahoo consensus positivo ({bullish*100:.0f}% Buy/Strong Buy)")
                elif bearish >= 0.25:
                    risks.append(f"🔴 Quota Sell/Strong Sell elevata ({bearish*100:.0f}%)")
                else:
                    score += 2
                    reasons.append("🟡 Consensus analisti misto")
    except Exception:
        pass

    # Finnhub aggiunge conferma solo US; non deve gonfiare oltre il massimo.
    fscore, freasons = finnhub_recommendation_score_us(symbol)
    if fscore > 0:
        score += min(4, fscore // 2)
        reasons.extend(freasons)
    elif fscore < 0:
        risks.extend(freasons)

    return int(clamp(score, 0, 20)), target, upside, reasons, risks


# ============================================================
# REVISIONI EPS / RICAVI 0..15
# ============================================================
def estimates_component(stock: yf.Ticker) -> Tuple[int, List[str], List[str]]:
    reasons, risks = [], []
    score = 0

    # EPS revisions
    try:
        rev = stock.get_eps_revisions()
        if isinstance(rev, pd.DataFrame) and not rev.empty:
            # preferisce trimestre corrente (0q), altrimenti prima riga
            row = rev.loc["0q"] if "0q" in rev.index else rev.iloc[0]
            up7 = safe_float(row.get("upLast7days")) or 0
            up30 = safe_float(row.get("upLast30days")) or 0
            down7 = safe_float(row.get("downLast7Days")) or safe_float(row.get("downLast7days")) or 0
            down30 = safe_float(row.get("downLast30Days")) or safe_float(row.get("downLast30days")) or 0
            net = (up7 + up30) - (down7 + down30)
            if net >= 4:
                score += 8
                reasons.append("🟢 Revisioni EPS nettamente positive")
            elif net >= 1:
                score += 5
                reasons.append("🟢 Revisioni EPS positive")
            elif net <= -3:
                risks.append("🔴 Revisioni EPS negative")
    except Exception:
        pass

    # Earnings estimate growth
    try:
        ee = stock.get_earnings_estimate()
        if isinstance(ee, pd.DataFrame) and not ee.empty:
            row = ee.loc["0q"] if "0q" in ee.index else ee.iloc[0]
            growth = safe_float(row.get("growth"))
            if growth is not None:
                # Yahoo solitamente usa frazione, es. 0.12 = 12%
                if growth >= 0.15:
                    score += 4
                    reasons.append(f"🟢 Crescita EPS attesa +{growth*100:.1f}%")
                elif growth >= 0.05:
                    score += 2
                    reasons.append(f"🟢 Crescita EPS attesa +{growth*100:.1f}%")
                elif growth < -0.10:
                    risks.append(f"🔴 EPS atteso in calo {growth*100:.1f}%")
    except Exception:
        pass

    # Revenue estimate growth
    try:
        re = stock.get_revenue_estimate()
        if isinstance(re, pd.DataFrame) and not re.empty:
            row = re.loc["0q"] if "0q" in re.index else re.iloc[0]
            growth = safe_float(row.get("growth"))
            if growth is not None:
                if growth >= 0.10:
                    score += 3
                    reasons.append(f"🟢 Crescita ricavi attesa +{growth*100:.1f}%")
                elif growth >= 0.03:
                    score += 1
                    reasons.append(f"🟢 Ricavi attesi +{growth*100:.1f}%")
                elif growth < -0.08:
                    risks.append(f"🔴 Ricavi attesi in calo {growth*100:.1f}%")
    except Exception:
        pass

    return int(clamp(score, 0, 15)), reasons, risks


# ============================================================
# NEWS SENTIMENT / UPGRADE 0..10
# Evita NLP inventato: usa solo segnali strutturati quando disponibili.
# ============================================================
def sentiment_component(stock: yf.Ticker) -> Tuple[int, List[str], List[str]]:
    reasons, risks = [], []
    score = 0
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)

    try:
        ud = stock.get_upgrades_downgrades()
        if isinstance(ud, pd.DataFrame) and not ud.empty:
            recent = ud.copy()
            try:
                idx = pd.to_datetime(recent.index, utc=True)
                recent = recent[idx >= cutoff]
            except Exception:
                recent = recent.head(20)

            upgrades = 0
            downgrades = 0
            for _, row in recent.head(20).iterrows():
                action = str(row.get("action", "")).lower()
                if "up" in action:
                    upgrades += 1
                elif "down" in action:
                    downgrades += 1

            net = upgrades - downgrades
            if net >= 3:
                score += 7
                reasons.append(f"🟢 Upgrade analisti recenti: {upgrades} vs downgrade {downgrades}")
            elif net >= 1:
                score += 4
                reasons.append(f"🟢 Upgrade analisti prevalenti: {upgrades} vs {downgrades}")
            elif net <= -2:
                risks.append(f"🔴 Downgrade analisti prevalenti: {downgrades} vs {upgrades}")
    except Exception:
        pass

    # News count come conferma di attenzione, non come sentiment semantico.
    try:
        news = stock.news or []
        recent_count = 0
        for item in news[:30]:
            ts = item.get("providerPublishTime")
            if ts:
                d = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
                if d >= cutoff:
                    recent_count += 1
        if recent_count >= 8:
            score += 3
            reasons.append(f"📰 Elevata attenzione informativa: {recent_count} news recenti")
        elif recent_count >= 3:
            score += 1
    except Exception:
        pass

    return int(clamp(score, 0, 10)), reasons, risks



# ============================================================
# CATALYST INTELLIGENCE: EVENTI SOCIETARI / GOVERNATIVI 0..30
# Usa solo titoli/metadata delle news: niente affermazioni inventate.
# Un progetto/gara viene marcato come POTENZIALE finché non è assegnato.
# ============================================================
CONFIRMED_CONTRACT_PATTERNS = [
    r"\bawarded\b.*\bcontract\b", r"\bwins?\b.*\bcontract\b",
    r"\bcontract\b.*\bawarded\b", r"\bselected\b.*\bcontract\b",
    r"\breceives?\b.*\border\b", r"\bsecures?\b.*\border\b",
    r"\bframework agreement\b", r"\bauftrag erhalten\b",
    r"\bcontrat.*attribu", r"\baggiudica.*contratt", r"\bcommessa.*assegnat",
]
GOV_WORDS = [
    "government", "ministry", "department of defense", "department of defence",
    "pentagon", "nato", "state", "public procurement", "public sector",
    "eu commission", "european commission", "federal", "defence", "defense",
    "governo", "ministero", "stato", "pubblica amministrazione", "ue",
]
PROJECT_WORDS = [
    "tender", "bid", "proposal", "submitted", "project", "programme", "program",
    "procurement", "funding", "grant", "rfp", "gara", "bando", "progetto",
    "offerta", "finanziamento", "stanziamento",
]
GUIDANCE_POS = [
    "raises guidance", "raises outlook", "lifts guidance", "lifts outlook",
    "upgrades guidance", "guidance raised", "boosts forecast", "alza la guidance",
]
GUIDANCE_NEG = [
    "cuts guidance", "lowers guidance", "cuts outlook", "profit warning",
    "guidance cut", "taglia la guidance", "riduce la guidance",
]
REGULATORY_POS = [
    "fda approval", "fda approves", "ema approval", "approved by fda",
    "regulatory approval", "authorization granted", "authorisation granted",
    "approvazione fda", "approvazione ema", "autorizzazione concessa",
]
MNA_POS = [
    "acquisition", "to acquire", "merger agreement", "takeover offer",
    "strategic review", "acquisizione", "fusione", "opa",
]
CAPITAL_RETURN_POS = [
    "share buyback", "stock buyback", "repurchase program", "repurchase programme",
    "buyback program", "riacquisto azioni", "buyback",
]
PARTNERSHIP_POS = [
    "strategic partnership", "partnership with", "joint venture", "collaboration with",
    "partnership strategica", "joint venture con", "accordo strategico",
]
ORDER_BACKLOG_POS = [
    "record backlog", "order backlog", "order intake", "record orders",
    "backlog record", "portafoglio ordini", "nuovi ordini", "record di ordini",
]
NEGATIVE_EVENT_WORDS = [
    "contract cancelled", "contract canceled", "loses contract", "investigation",
    "accounting probe", "fraud probe", "bankruptcy", "chapter 11", "share offering",
    "secondary offering", "dilution", "recall", "suspends guidance",
]


def _news_fields(item: dict) -> Tuple[str, str, Optional[dt.datetime], str]:
    """Compatibile con vecchio e nuovo formato yfinance news."""
    if not isinstance(item, dict):
        return "", "", None, ""
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    title = str(content.get("title") or item.get("title") or "").strip()
    summary = str(content.get("summary") or content.get("description") or item.get("summary") or "").strip()
    provider = content.get("provider")
    if isinstance(provider, dict):
        source = str(provider.get("displayName") or provider.get("name") or "Yahoo Finance")
    else:
        source = str(item.get("publisher") or content.get("publisher") or "Yahoo Finance")

    published = None
    raw = content.get("pubDate") or content.get("displayTime") or item.get("providerPublishTime")
    try:
        if isinstance(raw, (int, float)):
            published = dt.datetime.fromtimestamp(raw, tz=dt.timezone.utc)
        elif raw:
            ts = pd.to_datetime(raw, utc=True)
            published = ts.to_pydatetime()
    except Exception:
        published = None
    return title, summary, published, source


def _contains_any(text: str, words: List[str]) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def _matches_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def event_intelligence_component(stock: yf.Ticker) -> Tuple[int, List[str], List[str], bool, Optional[str], Optional[str]]:
    """0..30. Analizza eventi concreti nelle news recenti.

    Restituisce anche un flag SPECIAL e il miglior evento da mostrare nel report.
    La classificazione è euristica: il testo Telegram lo presenta come segnale,
    non come certezza su ordini/profitti futuri.
    """
    score = 0
    reasons: List[str] = []
    risks: List[str] = []
    special = False
    best_summary = None
    best_source = None
    best_event_points = -999
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=NEWS_LOOKBACK_DAYS)

    try:
        news = stock.news or []
    except Exception:
        news = []

    seen_titles = set()
    for item in news[:40]:
        title, summary, published, source = _news_fields(item)
        if not title:
            continue
        key = re.sub(r"\W+", "", title.lower())
        if key in seen_titles:
            continue
        seen_titles.add(key)
        if published and published < cutoff:
            continue

        text = f"{title}. {summary}".strip()
        low = text.lower()
        event_points = 0
        label = None

        if _contains_any(low, NEGATIVE_EVENT_WORDS) or _contains_any(low, GUIDANCE_NEG):
            risks.append(f"🔴 Evento/news da verificare: {title[:180]}")
            event_points -= 8

        # Contratto/ordine già annunciato: fatto più forte di una semplice candidatura.
        if _matches_any(text, CONFIRMED_CONTRACT_PATTERNS):
            gov = _contains_any(low, GOV_WORDS)
            event_points += 15 if gov else 12
            label = "🏛️ Contratto/ordine annunciato" if gov else "📦 Contratto/ordine annunciato"
            special = True

        # Progetto/gara/government funding: solo POTENZIALE, mai presentato come assegnazione.
        elif _contains_any(low, GOV_WORDS) and _contains_any(low, PROJECT_WORDS):
            event_points += 10
            label = "🟠 Catalyst governativo POTENZIALE"
            special = True

        if _contains_any(low, GUIDANCE_POS):
            event_points += 9
            label = label or "📈 Guidance/outlook migliorati"
            special = True
        if _contains_any(low, REGULATORY_POS):
            event_points += 10
            label = label or "🧪 Approvazione regolatoria"
            special = True
        if _contains_any(low, ORDER_BACKLOG_POS):
            event_points += 7
            label = label or "🏭 Ordini/backlog in miglioramento"
        if _contains_any(low, CAPITAL_RETURN_POS):
            event_points += 5
            label = label or "💰 Buyback/ritorno di capitale"
        if _contains_any(low, PARTNERSHIP_POS):
            event_points += 5
            label = label or "🤝 Partnership strategica"
        if _contains_any(low, MNA_POS):
            event_points += 6
            label = label or "🔄 M&A / operazione straordinaria"

        # Evita che una sola news con molte keyword saturi lo score.
        event_points = int(clamp(event_points, -10, 15))
        if event_points > 0 and label:
            reasons.append(f"{label}: {title[:170]}")
        if event_points > best_event_points and event_points > 0:
            best_event_points = event_points
            best_summary = f"{label}: {title[:220]}" if label else title[:220]
            best_source = source

        score += max(0, event_points)

    return int(clamp(score, 0, 30)), reasons[:6], risks[:4], special, best_summary, best_source


# ============================================================
# FONDAMENTALI 0..10
# Non sostituisce un'analisi di bilancio: usa metriche Yahoo disponibili.
# ============================================================
def fundamental_component(stock: yf.Ticker) -> Tuple[int, List[str], List[str]]:
    score = 0
    reasons: List[str] = []
    risks: List[str] = []
    try:
        info = stock.info or {}
    except Exception:
        info = {}

    rev_growth = safe_float(info.get("revenueGrowth"))
    earn_growth = safe_float(info.get("earningsGrowth"))
    op_margin = safe_float(info.get("operatingMargins"))
    fcf = safe_float(info.get("freeCashflow"))
    debt_eq = safe_float(info.get("debtToEquity"))

    if rev_growth is not None:
        if rev_growth >= 0.12:
            score += 3; reasons.append(f"🟢 Ricavi in crescita +{rev_growth*100:.1f}%")
        elif rev_growth >= 0.04:
            score += 2
        elif rev_growth < -0.08:
            risks.append(f"🔴 Ricavi in calo {rev_growth*100:.1f}%")
    if earn_growth is not None:
        if earn_growth >= 0.15:
            score += 3; reasons.append(f"🟢 Utili in crescita +{earn_growth*100:.1f}%")
        elif earn_growth >= 0.05:
            score += 2
        elif earn_growth < -0.10:
            risks.append(f"🔴 Utili in calo {earn_growth*100:.1f}%")
    if op_margin is not None and op_margin > 0.15:
        score += 2; reasons.append(f"🟢 Margine operativo {op_margin*100:.1f}%")
    if fcf is not None and fcf > 0:
        score += 2; reasons.append("🟢 Free cash flow positivo")
    if debt_eq is not None and debt_eq > 250:
        risks.append(f"⚠️ Debito/equity elevato ({debt_eq:.0f}%)")

    return int(clamp(score, 0, 10)), reasons, risks


# ============================================================
# CATALYST CALENDARIO 0..10
# ============================================================
def catalyst_component(catalyst: Catalyst) -> Tuple[int, List[str], List[str]]:
    reasons, risks = [], []
    score = 0

    if catalyst.kind == "Trimestrale":
        score += 5
    elif catalyst.kind == "Ex-dividend":
        score += 2

    if catalyst.confidence == "VERIFIED":
        score += 3
        reasons.append("✅ Data catalyst verificata da 2 fonti")
    elif catalyst.confidence == "SINGLE_SOURCE":
        score += 2
        reasons.append(f"🟡 Data catalyst da una fonte: {', '.join(catalyst.sources)}")
    else:
        risks.append("🔴 Data catalyst in conflitto")

    if 1 <= catalyst.days_left <= 14:
        score += 2
        reasons.append(f"📅 Catalyst vicino: tra {catalyst.days_left} giorni")
    elif 15 <= catalyst.days_left <= LOOKAHEAD_DAYS:
        score += 1
        reasons.append(f"📅 Catalyst tra {catalyst.days_left} giorni")

    return int(clamp(score, 0, 10)), reasons, risks


# ============================================================
# ANALISI COMPLETA
# ============================================================
def analyze_stock(symbol: str, market: str) -> Optional[AnalysisResult]:
    print(f"\n--- {symbol} | {market} ---")
    stock = yf.Ticker(symbol)

    # FASE 1 - catalyst calendario + intelligence news. Se non c'è nulla di concreto,
    # evitiamo le chiamate più costose dell'analisi completa.
    catalyst = find_best_catalyst(symbol, stock)
    event_score, er, ek, special, event_summary, event_source = event_intelligence_component(stock)

    if catalyst is None and event_score < 5:
        print("Nessun catalyst calendario o evento strategico sufficiente.")
        return None

    # Se l'evento news è il solo catalyst, creiamo un catalyst strategico di oggi.
    if catalyst is None:
        today = dt.date.today()
        catalyst = Catalyst(
            kind="Catalyst strategico",
            date=today,
            days_left=0,
            confidence="SINGLE_SOURCE",
            sources=[event_source or "News Yahoo Finance"],
            details=event_summary or "Evento societario recente",
        )

    try:
        df = stock.history(period="1y", interval="1d", auto_adjust=False)
    except Exception as exc:
        print(f"history error: {exc}")
        return None
    if df is None or df.empty or len(df) < MIN_HISTORY_ROWS:
        print("Storico insufficiente")
        return None

    df = calculate_indicators(df)
    latest = df.iloc[-1]
    current_price = safe_float(latest.get("Close"))
    if not current_price or current_price <= 0:
        return None

    try:
        info = stock.info or {}
        name = info.get("shortName") or info.get("longName") or symbol
    except Exception:
        name = symbol
    isin = get_isin_safe(stock)

    # Componenti originarie riscalate ai nuovi pesi.
    tech25, r1, k1 = technical_component(df)
    mom10, r2, k2 = momentum_component(df)
    analyst20, target, upside, r3, k3 = analyst_component(stock, symbol, current_price)
    est15, r4, k4 = estimates_component(stock)
    cal10, r5, k5 = catalyst_component(catalyst)
    sent10, r6, k6 = sentiment_component(stock)
    fund10, r7, k7 = fundamental_component(stock)

    technical_score = round(tech25 * 15 / 25)
    momentum_score = round(mom10 * 5 / 10)
    analyst_score = round(analyst20 * 10 / 20)
    estimates_score = round(est15 * 10 / 15)
    catalyst_score = cal10
    sentiment_score = sent10
    fundamental_score = fund10

    raw_score = (
        technical_score + analyst_score + estimates_score + catalyst_score +
        event_score + fundamental_score + momentum_score + sentiment_score
    )

    penalty = 0
    if catalyst.confidence == "SINGLE_SOURCE" and catalyst.kind == "Trimestrale":
        penalty += 2
    if upside is not None and upside < -5:
        penalty += 5
    if len(k1) >= 2:
        penalty += 2
    # Un semplice progetto/gara non può da solo trasformare un titolo mediocre in 5 stelle.
    if special and event_summary and "POTENZIALE" in event_summary.upper() and technical_score < 7:
        penalty += 3

    score = int(clamp(raw_score - penalty, 0, 100))
    stars = score_to_stars(score)
    reasons = er + r1 + r2 + r3 + r4 + r5 + r6 + r7
    risks = ek + k1 + k2 + k3 + k4 + k5 + k6 + k7

    print(
        f"score={score} tech={technical_score}/15 analyst={analyst_score}/10 "
        f"est={estimates_score}/10 cal={catalyst_score}/10 events={event_score}/30 "
        f"fund={fundamental_score}/10 mom={momentum_score}/5 news={sentiment_score}/10"
    )

    return AnalysisResult(
        symbol=symbol, name=str(name), isin=isin, market=market, score=score, stars=stars,
        catalyst=catalyst, technical_score=technical_score, analyst_score=analyst_score,
        estimates_score=estimates_score, catalyst_score=catalyst_score,
        momentum_score=momentum_score, sentiment_score=sentiment_score,
        event_score=event_score, fundamental_score=fundamental_score,
        special_catalyst=special, event_summary=event_summary, event_source=event_source,
        current_price=current_price, target_price=target, upside_pct=upside,
        reasons=reasons, risks=risks,
    )


# ============================================================
# TELEGRAM
# ============================================================
def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram non configurato; report stampato soltanto a console.")
        print(message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    ok = True

    # Telegram ha limiti di lunghezza: spezza in chunk sicuri.
    chunks = []
    remaining = message
    while len(remaining) > 3900:
        cut = remaining.rfind("\n\n", 0, 3900)
        if cut < 1000:
            cut = 3900
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    chunks.append(remaining)

    for chat_id in [x.strip() for x in TELEGRAM_CHAT_ID.split(",") if x.strip()]:
        for chunk in chunks:
            try:
                r = requests.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                    timeout=15,
                )
                if r.status_code != 200:
                    ok = False
                    print(f"Telegram {chat_id}: HTTP {r.status_code}: {r.text[:300]}")
            except Exception as exc:
                ok = False
                print(f"Telegram {chat_id}: {exc}")
    return ok


# ============================================================
# REPORT
# ============================================================
def fmt_price(x: Optional[float]) -> str:
    return "N/D" if x is None else f"{x:.2f}"


def build_report(results: List[AnalysisResult], scanned: int, catalysts_found: int) -> str:
    today = dt.date.today()
    if not results:
        return (
            "✅ *SCANSIONE BORSA COMPLETATA*\n\n"
            f"📅 {today.strftime('%d/%m/%Y')}\n"
            f"🔎 Titoli unici analizzati: *{scanned}*\n"
            f"🔥 Titoli con catalyst/evento rilevante: *{catalysts_found}*\n\n"
            "📊 *Nessuna opportunità da 4/5 o 5/5 oggi.*\n\n"
            f"Soglia minima: *{MIN_SCORE}/100*. Nessun titolo viene inserito per riempire il report."
        )

    special_count = sum(1 for r in results if r.special_catalyst)
    report = (
        "🚀 *TOP OPPORTUNITÀ BORSA — GLOBAL CATALYST*\n"
        f"📅 {today.strftime('%d/%m/%Y')}\n"
        f"🎯 Solo rating ≥ *{MIN_SCORE}/100*\n"
        f"🔥 Catalyst Special tra i finalisti: *{special_count}*\n\n"
    )

    for i, r in enumerate(results[:TOP_N], start=1):
        stars = "⭐" * r.stars
        confidence = {"VERIFIED":"✅ verificata", "SINGLE_SOURCE":"🟡 singola fonte", "CONFLICT":"🔴 conflitto"}.get(r.catalyst.confidence, r.catalyst.confidence)
        if r.special_catalyst:
            report += "🚨 *CATALYST SPECIAL*\n"

        report += (
            f"*#{i} {r.name}* (`{r.symbol}`)\n"
            f"🆔 ISIN: `{r.isin or 'N/D'}`\n"
            f"{r.market}\n{stars} *{r.score}/100*\n\n"
        )

        if r.event_summary:
            report += (
                f"🔥 *Evento rilevato:* {r.event_summary}\n"
                f"📰 Fonte news: {r.event_source or 'N/D'}\n"
            )
            if "POTENZIALE" in r.event_summary.upper():
                report += "⚠️ *Stato:* opportunità potenziale; contratto/ordine NON considerato assegnato.\n"
            report += "\n"

        report += (
            f"📅 *Catalyst calendario:* {r.catalyst.kind} — {r.catalyst.date.strftime('%d/%m/%Y')}\n"
            f"🔐 Affidabilità: {confidence} — {', '.join(r.catalyst.sources)}\n\n"
            f"📈 Tecnica: *{r.technical_score}/15*\n"
            f"🧠 Analisti/target: *{r.analyst_score}/10*\n"
            f"📊 Stime/revisioni: *{r.estimates_score}/10*\n"
            f"📅 Catalyst calendario: *{r.catalyst_score}/10*\n"
            f"🏛️ Eventi/contratti/progetti: *{r.event_score}/30*\n"
            f"💼 Fondamentali: *{r.fundamental_score}/10*\n"
            f"🔥 Momentum/volume: *{r.momentum_score}/5*\n"
            f"📰 Upgrade/news: *{r.sentiment_score}/10*\n\n"
            f"💵 Prezzo: *{fmt_price(r.current_price)}*\n"
        )
        if r.target_price is not None:
            report += f"🎯 Target medio: *{fmt_price(r.target_price)}*"
            if r.upside_pct is not None:
                sign = "+" if r.upside_pct >= 0 else ""
                report += f" ({sign}{r.upside_pct:.1f}%)"
            report += "\n"

        if r.reasons:
            report += "\n*Perché è in classifica:*\n"
            for reason in r.reasons[:7]:
                report += f"• {reason}\n"
        if r.risks:
            report += "\n*Rischi / elementi da verificare:*\n"
            for risk in r.risks[:3]:
                report += f"• {risk}\n"
        report += "\n——————————————\n\n"

    report += (
        f"Titoli con catalyst/eventi trovati: *{catalysts_found}*\n"
        f"Titoli mostrati: *{min(len(results), TOP_N)}*\n\n"
        "⚠️ Lo scanner classifica automaticamente dati e titoli di news. "
        "Una gara, proposta o progetto viene trattato come potenziale finché una fonte non comunica l'assegnazione. "
        "Non costituisce consulenza finanziaria."
    )
    return report


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 70)
    print("MARKET OPPORTUNITY SCANNER 4.0 — GLOBAL CATALYST")
    print("MERCATI GLOBALI + MID-CAP + CATALYST INTELLIGENCE + ISIN")
    print("Solo opportunità 4/5 e 5/5")
    print("=" * 70)

    global MARKETS
    MARKETS = build_markets()
    print("Mercati caricati:")
    for market, tickers in MARKETS.items():
        print(f"  {market}: {len(tickers)}")

    universe = unique_universe(MARKETS)
    results: List[AnalysisResult] = []
    catalysts_found = 0

    for idx, (symbol, market) in enumerate(universe, start=1):
        print(f"[{idx}/{len(universe)}] {symbol}")
        try:
            result = analyze_stock(symbol, market)
            if result is not None:
                catalysts_found += 1
                # SOLO rialzisti forti: niente 1/5 e 2/5.
                if result.score >= MIN_SCORE and result.stars >= 4:
                    results.append(result)
        except Exception as exc:
            print(f"Errore {symbol}: {exc}")

        if REQUEST_SLEEP > 0:
            time.sleep(REQUEST_SLEEP)

    # Deduplica anche la stessa società presente con ticker/quotazioni diverse.
    before_dedupe = len(results)
    results = dedupe_company_results(results)
    print(f"Deduplica società: {before_dedupe} -> {len(results)}")

    # Migliori prima. A parità di score preferiamo catalyst verificato e più vicino.
    results.sort(
        key=lambda r: (
            r.score,
            1 if r.catalyst.confidence == "VERIFIED" else 0,
            -r.catalyst.days_left,
        ),
        reverse=True,
    )

    # Limita davvero il report ai migliori.
    results = results[:TOP_N]

    report = build_report(
        results=results,
        scanned=len(universe),
        catalysts_found=catalysts_found,
    )

    print("\n" + report)
    send_telegram(report)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = f"🔴 *SCANNER BORSA - ERRORE*\n\n`{str(exc)[:800]}`"
        print(msg)
        try:
            send_telegram(msg)
        except Exception:
            pass
