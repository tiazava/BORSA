import os
import requests
import datetime
import pandas as pd
import yfinance as yf


# ============================================================
# CONFIGURAZIONE
# ============================================================

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# ============================================================
# COMPONENTI FTSE MIB
# ============================================================

FTSE_MIB = [
    "A2A.MI",
    "AMP.MI",
    "ARISTON.MI",
    "AZM.MI",
    "BAMI.MI",
    "BCA.MI",
    "BPE.MI",
    "BZZ.MI",
    "CPR.MI",
    "DIA.MI",
    "ENEL.MI",
    "ENI.MI",
    "ERG.MI",
    "RACE.MI",
    "FBK.MI",
    "G.MI",
    "HER.MI",
    "INW.MI",
    "ISP.MI",
    "LDO.MI",
    "MB.MI",
    "MONC.MI",
    "NEXI.MI",
    "PIR.MI",
    "PNT.MI",
    "PRY.MI",
    "REC.MI",
    "RWAY.MI",
    "SRG.MI",
    "STLAM.MI",
    "STMMI.MI",
    "TIT.MI",
    "TEN.MI",
    "TRN.MI",
    "UCG.MI",
    "US.MI",
]


# ============================================================
# COMPONENTI DOW JONES
# ============================================================

DOW_JONES = [
    "AAPL",
    "AMGN",
    "AMZN",
    "AXP",
    "BA",
    "CAT",
    "CRM",
    "CSCO",
    "CVX",
    "DIS",
    "DOW",
    "GS",
    "HD",
    "HON",
    "IBM",
    "INTC",
    "JNJ",
    "JPM",
    "KO",
    "MCD",
    "MMM",
    "MRK",
    "MSFT",
    "NKE",
    "PG",
    "TRV",
    "UNH",
    "V",
    "VZ",
    "WMT",
]


# ============================================================
# FUNZIONE HTTP GENERICA FINNHUB
# ============================================================

def finnhub_get(endpoint, params=None):
    """
    Effettua una richiesta alle API Finnhub.
    Restituisce un dizionario/lista oppure None in caso di errore.
    """

    if not FINNHUB_API_KEY:
        print("ERRORE: FINNHUB_API_KEY non configurata.")
        return None

    if params is None:
        params = {}

    params["token"] = FINNHUB_API_KEY

    url = f"https://finnhub.io/api/v1/{endpoint}"

    try:
        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        if response.status_code != 200:
            print(
                f"Finnhub HTTP {response.status_code} "
                f"per endpoint {endpoint}"
            )
            return None

        return response.json()

    except requests.exceptions.Timeout:
        print(f"Timeout Finnhub: {endpoint}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"Errore connessione Finnhub: {e}")
        return None

    except ValueError:
        print(f"Risposta JSON non valida da Finnhub: {endpoint}")
        return None


# ============================================================
# CALENDARIO TRIMESTRALI
# ============================================================

def get_upcoming_earnings(days_ahead=30):
    """
    Recupera le date delle prossime trimestrali da Finnhub.
    """

    today = datetime.date.today()
    future = today + datetime.timedelta(days=days_ahead)

    data = finnhub_get(
        "calendar/earnings",
        {
            "from": today.isoformat(),
            "to": future.isoformat(),
        }
    )

    if not data:
        print("Nessun dato ricevuto dal calendario Finnhub.")
        return []

    earnings = data.get("earningsCalendar", [])

    print(
        f"Calendario trimestrali: "
        f"{len(earnings)} eventi trovati."
    )

    return earnings


# ============================================================
# INSIDER TRADING
# ============================================================

def check_insider_trading(ticker_symbol):
    """
    Analizza le ultime transazioni insider disponibili.
    """

    clean_ticker = ticker_symbol.replace(".MI", "")

    data = finnhub_get(
        "stock/insider-transactions",
        {
            "symbol": clean_ticker
        }
    )

    if not data:
        return {
            "status": "NEUTRAL",
            "msg": None
        }

    transactions = data.get("data", [])

    if not transactions:
        return {
            "status": "NEUTRAL",
            "msg": None
        }

    net_shares = 0
    recent_buys = 0
    recent_sells = 0

    for item in transactions[:20]:

        try:
            change = float(item.get("change", 0) or 0)
        except (ValueError, TypeError):
            change = 0

        if change > 0:
            net_shares += change
            recent_buys += 1

        elif change < 0:
            net_shares += change
            recent_sells += 1

    if recent_buys > recent_sells and net_shares > 0:
        return {
            "status": "BUY",
            "msg": (
                "🟢 Insider Buying: "
                "i dirigenti stanno acquistando azioni proprie"
            )
        }

    if recent_sells > recent_buys and net_shares < 0:
        return {
            "status": "SELL",
            "msg": (
                "🔴 Insider Selling: "
                "i dirigenti stanno alleggerendo le posizioni"
            )
        }

    return {
        "status": "NEUTRAL",
        "msg": None
    }


# ============================================================
# SHORT INTEREST
# ============================================================

def check_short_interest(stock_info):
    """
    Analizza lo short interest disponibile nei dati Yahoo Finance.
    """

    if not isinstance(stock_info, dict):
        return {
            "high_short": False,
            "msg": None
        }

    try:
        short_percent = stock_info.get(
            "shortPercentOfFloat",
            0
        )

        if short_percent is None:
            short_percent = 0

        short_percent = float(short_percent)

        if short_percent > 0.05:
            return {
                "high_short": True,
                "msg": (
                    f"⚡ Alto Short Interest "
                    f"({short_percent * 100:.1f}%): "
                    f"possibile pressione rialzista in caso di catalizzatore positivo"
                )
            }

    except (ValueError, TypeError):
        pass

    return {
        "high_short": False,
        "msg": None
    }


# ============================================================
# CAMBIAMENTI EXECUTIVE
# ============================================================

def check_executive_changes(ticker_symbol):
    """
    Cerca cambiamenti recenti nei principali dirigenti.
    """

    clean_ticker = ticker_symbol.replace(".MI", "")

    data = finnhub_get(
        "stock/executive",
        {
            "symbol": clean_ticker
        }
    )

    if not data:
        return []

    executives = data.get("executive", [])

    if not executives:
        return []

    insights = []

    current_year = str(datetime.date.today().year)

    for executive in executives[:10]:

        position = str(
            executive.get("title", "")
        ).upper()

        name = executive.get(
            "name",
            "Nome non disponibile"
        )

        since = str(
            executive.get("since", "")
        )

        important_role = any(
            role in position
            for role in [
                "CEO",
                "CFO",
                "CHIEF EXECUTIVE",
                "CHIEF FINANCIAL",
                "PRESIDENT"
            ]
        )

        if important_role and current_year in since:

            insights.append(
                f"⚠️ Cambio vertici recente: "
                f"{name} ({executive.get('title', '')})"
            )

    return insights


# ============================================================
# ANALISI TITOLO
# ============================================================

def analyze_earnings_catalyst(
    ticker_symbol,
    release_date,
    market_name
):
    """
    Analizza il titolo in prossimità della trimestrale.

    Indicatori utilizzati:
    - SMA20
    - volume relativo
    - insider trading
    - short interest
    - cambiamenti executive
    """

    print(
        f"\nAnalisi {ticker_symbol} "
        f"- trimestrale {release_date}"
    )

    try:

        # ----------------------------------------------------
        # DOWNLOAD DATI YAHOO FINANCE
        # ----------------------------------------------------

        stock = yf.Ticker(ticker_symbol)

        df = stock.history(
            period="6mo",
            auto_adjust=False
        )

        if df.empty:
            print(
                f"{ticker_symbol}: nessun dato storico."
            )
            return None

        if len(df) < 20:
            print(
                f"{ticker_symbol}: dati insufficienti."
            )
            return None

        # ----------------------------------------------------
        # INFO TITOLO
        # ----------------------------------------------------

        try:
            info = stock.info
        except Exception as e:
            print(
                f"{ticker_symbol}: impossibile recuperare info: {e}"
            )
            info = {}

        if not isinstance(info, dict):
            info = {}

        # ----------------------------------------------------
        # DATA TRIMESTRALE
        # ----------------------------------------------------

        try:
            earnings_dt = datetime.datetime.strptime(
                str(release_date),
                "%Y-%m-%d"
            ).date()
        except ValueError:
            print(
                f"{ticker_symbol}: data trimestrale non valida: "
                f"{release_date}"
            )
            return None

        today = datetime.date.today()

        days_left = (
            earnings_dt - today
        ).days

        # ----------------------------------------------------
        # SMA20
        # ----------------------------------------------------

        df["SMA20"] = (
            df["Close"]
            .rolling(window=20)
            .mean()
        )

        latest = df.iloc[-1]

        close_price = latest.get("Close", 0)
        sma20 = latest.get("SMA20", 0)
        latest_volume = latest.get("Volume", 0)

        # ----------------------------------------------------
        # VOLUME MEDIO
        # ----------------------------------------------------

        volume_mean = (
            df["Volume"]
            .tail(20)
            .mean()
        )

        high_volume = False

        if (
            pd.notna(volume_mean)
            and volume_mean > 0
            and pd.notna(latest_volume)
        ):
            high_volume = (
                latest_volume > volume_mean * 1.20
            )

        # ----------------------------------------------------
        # INSIDER
        # ----------------------------------------------------

        insider_data = check_insider_trading(
            ticker_symbol
        )

        # ----------------------------------------------------
        # SHORT INTEREST
        # ----------------------------------------------------

        short_data = check_short_interest(
            info
        )

        # ----------------------------------------------------
        # EXECUTIVE
        # ----------------------------------------------------

        exec_news = check_executive_changes(
            ticker_symbol
        )

        # ====================================================
        # CALCOLO SCORE
        # ====================================================

        score = 3

        reasons = []

        # ----------------------------------------------------
        # TREND + VOLUME
        # ----------------------------------------------------

        if (
            pd.notna(sma20)
            and pd.notna(close_price)
        ):

            if close_price > sma20 and high_volume:

                score += 1

                reasons.append(
                    "🟢 Accumulo pre-bilancio: "
                    "prezzo sopra SMA20 con volume superiore "
                    "alla media"
                )

            elif close_price < sma20:

                score -= 1

                reasons.append(
                    "🔴 Trend debole: "
                    "prezzo sotto la SMA20"
                )

            elif close_price > sma20:

                reasons.append(
                    "🟢 Trend positivo: "
                    "prezzo sopra la SMA20"
                )

        # ----------------------------------------------------
        # INSIDER
        # ----------------------------------------------------

        if insider_data["msg"]:

            reasons.append(
                insider_data["msg"]
            )

            if insider_data["status"] == "BUY":
                score += 1

            elif insider_data["status"] == "SELL":
                score -= 1

        # ----------------------------------------------------
        # SHORT INTEREST
        # ----------------------------------------------------

        if short_data["msg"]:

            reasons.append(
                short_data["msg"]
            )

        # ----------------------------------------------------
        # CAMBI EXECUTIVE
        # ----------------------------------------------------

        if exec_news:

            reasons.extend(
                exec_news
            )

            if days_left <= 15:

                reasons.append(
                    "⚠️ Cambio vertici vicino "
                    "alla trimestrale: possibile aumento "
                    "della volatilità"
                )

        # ----------------------------------------------------
        # LIMITAZIONE SCORE
        # ----------------------------------------------------

        score = max(
            1,
            min(5, score)
        )

        # ====================================================
        # BIAS OPERATIVO
        # ====================================================

        if score >= 4:

            bias = (
                "🚀 SEGNALE RIALZISTA "
                "(Forte Potenziale)"
            )

            action_advice = (
                "💡 *Segnale:* "
                "Titolo in accumulo / possibile "
                "spinta positiva verso la trimestrale."
            )

        elif score <= 2:

            bias = (
                "🔻 SEGNALE RIBASSISTA "
                "(Alto Rischio)"
            )

            action_advice = (
                "💡 *Segnale:* "
                "Debolezza / possibile rischio "
                "di sell-off pre o post bilancio."
            )

        else:

            bias = "⚖️ NEUTRO"

            action_advice = (
                "💡 *Segnale:* "
                "Nessun vantaggio operativo chiaro "
                "al momento."
            )

        # ====================================================
        # NOME TITOLO
        # ====================================================

        name = info.get(
            "shortName",
            ticker_symbol
        )

        if not name:
            name = ticker_symbol

        # ====================================================
        # RISULTATO
        # ====================================================

        return {
            "symbol": ticker_symbol,
            "name": name,
            "market": market_name,
            "days_left": days_left,
            "release_date": release_date,
            "score": score,
            "bias": bias,
            "reasons": reasons,
            "advice": action_advice
        }

    except Exception as e:

        print(
            f"Errore durante l'analisi di "
            f"{ticker_symbol}: {e}"
        )

        return None


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram_message(message):
    """
    Invia il report a uno o più chat ID Telegram.
    """

    if not TELEGRAM_BOT_TOKEN:
        print(
            "ERRORE: TELEGRAM_BOT_TOKEN non configurato."
        )
        return False

    if not TELEGRAM_CHAT_ID:
        print(
            "ERRORE: TELEGRAM_CHAT_ID non configurato."
        )
        return False

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    chat_ids = TELEGRAM_CHAT_ID.split(",")

    success = True

    for chat_id in chat_ids:

        chat_id = chat_id.strip()

        if not chat_id:
            continue

        try:

            response = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                },
                timeout=15
            )

            if response.status_code == 200:

                print(
                    f"Telegram: messaggio inviato "
                    f"a {chat_id}"
                )

            else:

                success = False

                print(
                    f"Telegram errore "
                    f"{response.status_code}: "
                    f"{response.text}"
                )

        except requests.exceptions.RequestException as e:

            success = False

            print(
                f"Errore invio Telegram: {e}"
            )

    return success


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("AUTOMATIC TRADING SIGNALS")
    print("Earnings & Catalysts Scanner")
    print("=" * 60)

    try:

        # ====================================================
        # CONTROLLO API
        # ====================================================

        if not FINNHUB_API_KEY:

            print(
                "ERRORE: FINNHUB_API_KEY non configurata."
            )

            return

        # ====================================================
        # RECUPERA TRIMESTRALI
        # ====================================================

        upcoming_events = get_upcoming_earnings(
            days_ahead=30
        )

        if not upcoming_events:

            print(
                "Nessuna trimestrale trovata "
                "nel periodo analizzato."
            )

            return

        # ====================================================
        # CREA DIZIONARIO TRIMESTRALI
        # ====================================================

        upcoming_dict = {}

        for item in upcoming_events:

            symbol = item.get("symbol")
            release_date = item.get("date")

            if symbol and release_date:

                upcoming_dict[
                    symbol.upper()
                ] = release_date

        print(
            f"Eventi validi: "
            f"{len(upcoming_dict)}"
        )

        # ====================================================
        # IDENTIFICA TITOLI FTSE MIB
        # ====================================================

        targets = []

        for ticker in FTSE_MIB:

            clean_symbol = (
                ticker
                .replace(".MI", "")
                .upper()
            )

            if clean_symbol in upcoming_dict:

                targets.append(
                    (
                        ticker,
                        upcoming_dict[clean_symbol],
                        "🇮🇹 FTSE MIB"
                    )
                )

        # ====================================================
        # IDENTIFICA TITOLI DOW JONES
        # ====================================================

        for ticker in DOW_JONES:

            if ticker.upper() in upcoming_dict:

                targets.append(
                    (
                        ticker,
                        upcoming_dict[ticker.upper()],
                        "🇺🇸 DOW JONES"
                    )
                )

        print(
            f"Titoli da analizzare: "
            f"{len(targets)}"
        )

        # ====================================================
        # ANALISI
        # ====================================================

        signals = []

        for ticker, release_date, market in targets:

            try:

                analysis = analyze_earnings_catalyst(
                    ticker,
                    release_date,
                    market
                )

                if analysis:

                    score = analysis["score"]

                    if score >= 4 or score <= 2:

                        signals.append(
                            analysis
                        )

            except Exception as e:

                print(
                    f"Salto {ticker} "
                    f"per errore: {e}"
                )

                continue

        # ====================================================
        # NESSUN SEGNALE
        # ====================================================

        if not signals:

            print(
                "Nessun segnale ad alta priorità "
                "rilevato nella scansione odierna."
            )

            return

        # ====================================================
        # ORDINA I SEGNALI
        # ====================================================

        signals.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        # ====================================================
        # CREA REPORT
        # ====================================================

        report = (
            "🚨 *AUTOMATIC TRADING SIGNALS*\n"
            "*BILANCI & CATALIZZATORI*\n\n"
        )

        report += (
            f"📊 Segnali rilevati: "
            f"*{len(signals)}*\n\n"
        )

        for sig in signals:

            stars = (
                "⭐" * sig["score"]
            )

            report += (
                f"{sig['market']} | "
                f"*In uscita tra "
                f"{sig['days_left']} gg* "
                f"({sig['release_date']})\n"
            )

            report += (
                f"🏢 *{sig['name']}* "
                f"(`{sig['symbol']}`)\n"
            )

            report += (
                f"Rating: {stars} "
                f"({sig['score']}/5)\n"
            )

            report += (
                f"*{sig['bias']}*\n"
            )

            if sig["reasons"]:

                report += (
                    "Motivi del segnale:\n"
                )

                for reason in sig["reasons"]:

                    report += (
                        f"  • {reason}\n"
                    )

            report += (
                f"{sig['advice']}\n\n"
            )

        # ====================================================
        # INVIO TELEGRAM
        # ====================================================

        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:

            sent = send_telegram_message(
                report
            )

            if sent:

                print(
                    "Segnale inviato "
                    "correttamente su Telegram."
                )

            else:

                print(
                    "Errore durante l'invio "
                    "del report Telegram."
                )

        else:

            print(
                "Credenziali Telegram non rilevate."
            )

            print("\nREPORT:")
            print(report)

    except Exception as general_error:

        print(
            f"ERRORE GENERALE: "
            f"{general_error}"
        )


# ============================================================
# AVVIO
# ============================================================

if __name__ == "__main__":
    main()
