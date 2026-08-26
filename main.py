import os
import requests
import datetime
import yfinance as yf
import pandas_ta as ta

# Credenziali API
FINNHUB_API_KEY = "da7i359r01qj8fm71e5gda7i359r01qj8fm71e60"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Componenti FTSE MIB (Borsa Italiana)
FTSE_MIB = [
    "A2A.MI", "AMP.MI", "ARISTON.MI", "AZM.MI", "BAMI.MI", "BCA.MI", "BPE.MI", "BZZ.MI", 
    "CPR.MI", "DIA.MI", "ENEL.MI", "ENI.MI", "ERG.MI", "RACE.MI", "FBK.MI", "G.MI", 
    "HER.MI", "INW.MI", "ISP.MI", "LDO.MI", "MB.MI", "MONC.MI", "NEXI.MI", "PIR.MI", 
    "PNT.MI", "PRY.MI", "REC.MI", "RWAY.MI", "SRG.MI", "STLAM.MI", "STMMI.MI", "TIT.MI", 
    "TEN.MI", "TRN.MI", "UCG.MI", "US.MI"
]

# Componenti Dow Jones Industrial Average (USA)
DOW_JONES = [
    "AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", 
    "DOW", "GS", "HD", "HON", "IBM", "INTC", "JNJ", "JPM", "KO", "MCD", 
    "MMM", "MRK", "MSFT", "NKE", "PG", "TRV", "UNH", "V", "VZ", "WMT"
]

def get_upcoming_earnings(days_ahead=30):
    """Recupera le date delle prossime trimestrali da Finnhub."""
    today = datetime.date.today()
    future = today + datetime.timedelta(days=days_ahead)
    url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={future}&token={FINNHUB_API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        return res.get('earningsCalendar', [])
    except Exception as e:
        print(f"Errore recupero calendario Finnhub: {e}")
        return []

def check_insider_trading(ticker_symbol: str) -> dict:
    """Verifica le transazioni recenti dei dirigenti (Insider Trading)."""
    clean_ticker = ticker_symbol.replace(".MI", "")
    url = f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={clean_ticker}&token={FINNHUB_API_KEY}"
    try:
        res = requests.get(url, timeout=10).json()
        data = res.get('data', [])
        net_shares = 0
        recent_buys = 0
        recent_sells = 0

        for item in data[:10]: # Ultimi 10 movimenti dei dirigenti
            change = item.get('change', 0)
            if change > 0:
                net_shares += change
                recent_buys += 1
            elif change < 0:
                net_shares += change
                recent_sells += 1

        if recent_buys > recent_sells and net_shares > 0:
            return {"status": "BUY", "msg": "🟢 Insider Buying: I dirigenti stanno acquistando azioni proprie"}
        elif recent_sells > recent_buys and net_shares < 0:
            return {"status": "SELL", "msg": "🔴 Insider Selling: I dirigenti stanno alleggerendo le posizioni"}
    except Exception:
        pass
    return {"status": "NEUTRAL", "msg": None}

def check_short_interest(stock_info: dict) -> dict:
    """Analizza il livello di posizioni corte (Short Interest / PNC)."""
    try:
        short_percent = stock_info.get('shortPercentOfFloat', 0)
        if short_percent and short_percent > 0.05: # > 5% delle azioni in circolazione
            return {
                "high_short": True,
                "msg": f"⚡ Alto Short Interest ({short_percent*100:.1f}%): Possibile Short Squeeze se il bilancio è positivo"
            }
    except Exception:
        pass
    return {"high_short": False, "msg": None}

def check_executive_changes(ticker_symbol: str) -> list:
    """Verifica se ci sono stati cambi recenti nei vertici C-Suite (CEO/CFO)."""
    clean_ticker = ticker_symbol.replace(".MI", "")
    url = f"https://finnhub.io/api/v1/stock/executive?symbol={clean_ticker}&token={FINNHUB_API_KEY}"
    insights = []
    try:
        res = requests.get(url, timeout=10).json()
        executives = res.get('executive', [])
        for exec_info in executives[:5]:
            position = str(exec_info.get('title', '')).upper()
            since = exec_info.get('since', '')
            if any(role in position for role in ['CEO', 'CFO', 'CHIEF EXECUTIVE', 'CHIEF FINANCIAL', 'PRESIDENT']):
                if since and str(datetime.date.today().year) in str(since):
                    insights.append(f"Cambio vertici recente: {exec_info.get('name')} ({exec_info.get('title')})")
    except Exception:
        pass
    return insights

def analyze_earnings_catalyst(ticker_symbol: str, release_date: str, market_name: str) -> dict:
    """Analizza il titolo e genera il segnale in automatico."""
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="1y")
        
        if df.empty or len(df) < 50:
            return None

        info = stock.info
        today = datetime.date.today()
        earnings_dt = datetime.datetime.strptime(release_date, "%Y-%m-%d").date()
        days_left = (earnings_dt - today).days

        # 1. Analisi Tecnica e Volumi
        df['SMA20'] = ta.sma(df['Close'], length=20)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        latest = df.iloc[-1]
        vol_mean = df['Volume'].tail(20).mean()
        high_volume = latest['Volume'] > (vol_mean * 1.2)

        # 2. Insider Trading, Short Interest & C-Suite
        insider_data = check_insider_trading(ticker_symbol)
        short_data = check_short_interest(info)
        exec_news = check_executive_changes(ticker_symbol)

        # 3. Storico Trimestrali (Beat Rate)
        historical_beat = True
        try:
            earnings_history = stock.earnings_dates
            if earnings_history is not None and not earnings_history.empty:
                recent = earnings_history.dropna().head(4)
                if 'Reported EPS' in recent.columns and 'EPS Estimate' in recent.columns:
                    surprises = recent['Reported EPS'] > recent['EPS Estimate']
                    historical_beat = surprises.mean() >= 0.75
        except Exception:
            pass

        # 4. Calcolo Automatico del Punteggio (1 - 5)
        score = 3
        reasons = []

        if historical_beat:
            score += 1
            reasons.append("Storico solido: stime battute nelle ultime trimestrali")
        else:
            score -= 1
            reasons.append("Storico debole: rischio delusione stime utili")

        if latest['Close'] > df['SMA20'].iloc[-1] and high_volume:
            score += 1
            reasons.append("Accumulo pre-bilancio: volumi e prezzi in aumento")

        if insider_data['msg']:
            reasons.append(insider_data['msg'])
            if insider_data['status'] == "BUY":
                score += 1
            elif insider_data['status'] == "SELL":
                score -= 1

        if short_data['msg']:
            reasons.append(short_data['msg'])

        if exec_news:
            reasons.extend(exec_news)
            if days_left <= 15:
                reasons.append("⚠️ Cambio vertici vicino alla trimestrale (alta volatilità)")

        score = max(1, min(5, score))

        # Indicazione Operativa Automatica
        if score >= 4:
            bias = "🚀 SEGNALE RIALZISTA (Forte Potenziale)"
            action_advice = "💡 *Segnale:* Titolo in accumulo / possibile spinta alla trimestrale."
        elif score <= 2:
            bias = "🔻 SEGNALE RIBASSISTA (Alto Rischio)"
            action_advice = "💡 *Segnale:* Debolezza / Rischio sell-off pre o post bilancio."
        else:
            bias = "⚖️ NEUTRO"
            action_advice = "💡 *Segnale:* Nessun vantaggio operativo chiaro al momento."

        return {
            "symbol": ticker_symbol,
            "name": info.get('shortName', ticker_symbol),
            "market": market_name,
            "days_left": days_left,
            "release_date": release_date,
            "score": score,
            "bias": bias,
            "reasons": reasons,
            "advice": action_advice
        }
    except Exception as e:
        print(f"Errore durante l'analisi del titolo {ticker_symbol}: {e}")
        return None

def main():
    try:
        upcoming_events = get_upcoming_earnings(days_ahead=30)
        upcoming_dict = {item.get('symbol'): item.get('date') for item in upcoming_events if item.get('symbol')}

        targets = []
        for ticker in FTSE_MIB:
            clean_symbol = ticker.replace(".MI", "")
            if clean_symbol in upcoming_dict:
                targets.append((ticker, upcoming_dict[clean_symbol], "🇮🇹 FTSE MIB"))

        for ticker in DOW_JONES:
            if ticker in upcoming_dict:
                targets.append((ticker, upcoming_dict[ticker], "🇺🇸 DOW JONES"))

        signals = []

        # Scansione con gestione eccezioni per singolo titolo
        for ticker, release_date, market in targets:
            try:
                analysis = analyze_earnings_catalyst(ticker, release_date, market)
                # Invia solo se il punteggio è rilevante (>=4 o <=2)
                if analysis and (analysis['score'] >= 4 or analysis['score'] <= 2):
                    signals.append(analysis)
            except Exception as e:
                print(f"Errore salto ticker {ticker}: {e}")
                continue

        # Invio su Telegram solo se ci sono segnali rilevanti
        if signals:
            report = "🚨 *AUTOMATIC TRADING SIGNALS - BILANCI & CATALIZZATORI*\n\n"
            for sig in signals:
                stars = "⭐" * sig['score']
                report += f"{sig['market']} | *In uscita tra {sig['days_left']} gg* ({sig['release_date']})\n"
                report += f"🏢 *{sig['name']}* (`{sig['symbol']}`)\n"
                report += f"Rating: {stars} ({sig['score']}/5) | *{sig['bias']}*\n"
                report += "Motivi del segnale:\n"
                for r in sig['reasons']:
                    report += f"  • {r}\n"
                report += f"{sig['advice']}\n\n"

            if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
                chat_ids = TELEGRAM_CHAT_ID.split(",")
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                for cid in chat_ids:
                    requests.post(url, json={"chat_id": cid.strip(), "text": report, "parse_mode": "Markdown"}, timeout=10)
                print("Segnalazione Telegram inviata con successo.")
            else:
                print("Credenziali Telegram non configurate o vuote. Ecco l'output del report:")
                print(report)
        else:
            print("Nessun segnale ad alta priorità rilevato nella scansione odierna.")

    except Exception as general_error:
        print(f"Errore generale nell'esecuzione dello script: {general_error}")

if __name__ == "__main__":
    main()
