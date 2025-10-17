import os, time
import streamlit as st
import pandas as pd
import numpy as np

from storage import init_db, fetch_trades, fetch_positions, fetch_logs, DB_PATH
from bot_core import Bot

# ----- App State -----
if "bots" not in st.session_state:
    st.session_state["bots"] = {}  # symbol -> Bot instance

init_db()

st.set_page_config(page_title="Multi-Bot Binance (Spot)", layout="wide")
st.title("🤖📈 Multi-Bot Binance Spot — Dashboard")

with st.sidebar:
    st.header("Configuration globale (par défaut)")
    api_key = st.text_input("BINANCE_API_KEY", os.getenv("BINANCE_API_KEY",""), type="password")
    api_sec = st.text_input("BINANCE_API_SECRET", os.getenv("BINANCE_API_SECRET",""), type="password")
    default_testnet = st.checkbox("TESTNET par défaut", value=(os.getenv("TESTNET","true").lower() in ("1","true","yes")))
    default_dry = st.checkbox("DRY_RUN par défaut (pas d'ordres réels)", value=(os.getenv("DRY_RUN","true").lower() in ("1","true","yes")))

    st.divider()
    st.subheader("Nouveau bot")
    symbol = st.text_input("Symbole (ex. BTCUSDT)", "BTCUSDT")
    interval = st.selectbox("Intervalle", ["1m","3m","5m","15m","30m","1h","4h","1d"], index=0)
    risk_pct = st.slider("Risque (% du solde quote par trade)", 1, 50, 10) / 100.0
    max_pos = st.number_input("Plafond position (quote, 0=illimité)", min_value=0.0, value=0.0, step=10.0)

    # Per-bot mode selection
    st.markdown("**Mode du bot** (sélection spécifique à ce bot)")
    bot_mode = st.radio("Environnement", options=["TEST", "PROD"], horizontal=True, index=0)
    bot_dry = st.checkbox("DRY_RUN (journaliser sans ordres)", value=True)

    if st.button("Lancer le bot", type="primary", use_container_width=True):
        if not api_key or not api_sec:
            st.error("Renseigne API Key & Secret.")
        elif symbol in st.session_state["bots"] and st.session_state["bots"][symbol].is_alive():
            st.warning(f"Bot {symbol} déjà en cours.")
        else:
            testnet = (bot_mode == "TEST")
            dry_run = bot_dry
            bot = Bot(symbol=symbol, interval=interval, risk_pct=risk_pct, max_pos=max_pos,
                      testnet=testnet, dry_run=dry_run, api_key=api_key, api_secret=api_sec)
            bot.start()
            st.session_state["bots"][symbol] = bot
            st.success(f"Bot {symbol} lancé en mode {'TESTNET' if testnet else 'PROD'} (dry_run={dry_run}).")

st.subheader("Bots actifs")
hdr = st.columns([2,2,2,1,2,2])
hdr[0].markdown("**Symbole**")
hdr[1].markdown("**Statut**")
hdr[2].markdown("**Position**")
hdr[3].markdown("**Stop**")
hdr[4].markdown("**Relancer en TEST / PROD**")
hdr[5].markdown("**Logs**")

to_restart = []

for sym, bot in list(st.session_state["bots"].items()):
    status = "🟢 running" if bot.is_alive() else "🔴 stopped"
    pos = f"{bot.pos_side} {bot.pos_qty:.8f} @ {bot.entry_price:.4f}" if bot.pos_side=='LONG' else "FLAT"
    cols = st.columns([2,2,2,1,2,2])
    cols[0].write(sym)
    cols[1].write(status)
    cols[2].write(pos)

    # Stop
    if cols[3].button("Stop", key=f"stop_{sym}"):
        try:
            bot.stop()
        except Exception as e:
            st.error(f"Stop {sym} -> {e}")

    # Restart controls (per-bot mode)
    with cols[4]:
        c1, c2 = st.columns(2)
        if c1.button("TEST", key=f"restart_test_{sym}"):
            try:
                bot.stop()
                new_bot = Bot(symbol=sym, interval=bot.interval, risk_pct=bot.risk_pct, max_pos=bot.max_pos,
                              testnet=True, dry_run=True, api_key=bot.api_key, api_secret=bot.api_secret)
                new_bot.start()
                st.session_state["bots"][sym] = new_bot
                st.success(f"{sym} relancé en TESTNET (dry_run=True).")
            except Exception as e:
                st.error(f"Relance TEST {sym}: {e}")
        if c2.button("PROD", key=f"restart_prod_{sym}"):
            try:
                bot.stop()
                new_bot = Bot(symbol=sym, interval=bot.interval, risk_pct=bot.risk_pct, max_pos=bot.max_pos,
                              testnet=False, dry_run=False, api_key=bot.api_key, api_secret=bot.api_secret)
                new_bot.start()
                st.session_state["bots"][sym] = new_bot
                st.success(f"{sym} relancé en PROD (dry_run=False).")
            except Exception as e:
                st.error(f"Relance PROD {sym}: {e}")

    # Logs view
    if cols[5].button("Voir", key=f"logs_{sym}"):
        st.session_state["view_logs"] = sym

st.divider()
c1, c2 = st.columns(2)
with c1:
    st.subheader("Positions")
    pos = fetch_positions()
    st.dataframe(pd.DataFrame(pos))

with c2:
    st.subheader("Derniers trades")
    tr = fetch_trades()
    df = pd.DataFrame(tr)
    st.dataframe(df)

# ---- Equity / PnL graph ----
st.subheader("Graphe PnL réalisé (par bot)")
all_trades = fetch_trades()
symbols = sorted(list({t["symbol"] for t in all_trades})) if all_trades else []
sel = st.selectbox("Choisir un symbole pour le graph", options=symbols if symbols else ["(aucun)"])
if symbols and sel:
    tdf = pd.DataFrame([t for t in all_trades if t["symbol"]==sel])
    if not tdf.empty:
        # Keep only SELL trades with PnL (realized)
        sdf = tdf.dropna(subset=["pnl"]).copy()
        if not sdf.empty:
            sdf["ts"] = pd.to_datetime(sdf["ts"])
            sdf = sdf.sort_values("ts")
            sdf["cumpnl"] = sdf["pnl"].cumsum()
            st.line_chart(data=sdf.set_index("ts")["cumpnl"])
            # KPIs
            wins = (sdf["pnl"] > 0).sum()
            losses = (sdf["pnl"] <= 0).sum()
            total = int(wins + losses)
            wr = (wins/total*100.0) if total>0 else 0.0
            st.caption(f"Trades clôturés: {total} | Gagnants: {wins} | Perdants: {losses} | Win rate: {wr:.1f}% | PnL cumulé: {sdf['cumpnl'].iloc[-1]:.2f}")
        else:
            st.info("Aucun trade clôturé (SELL) avec PnL pour ce symbole.")
    else:
        st.info("Pas de trade pour ce symbole.")

st.subheader("Logs récents")
symbol_filter = st.text_input("Filtrer par symbole (optionnel)", value=os.getenv("SYMBOL",""))
logs = fetch_logs(symbol_filter if symbol_filter else None, limit=200)
st.dataframe(pd.DataFrame(logs))

st.caption(f"DB: {DB_PATH}")
