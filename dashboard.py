import os, time
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
from storage import (init_db, fetch_trades, fetch_positions, fetch_logs, DB_PATH,
                     save_running_bot, remove_running_bot, fetch_running_bots)
from bot_core import Bot
from backtest import run_backtest_async
from backtest_viz import create_backtest_chart, create_statistics_summary, create_trades_dataframe, create_production_chart
from realtime_viz import get_bot_realtime_data, create_realtime_chart

def _load_env_file(path: Path) -> bool:
    """Load key=value pairs from *path* into os.environ if not already set."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if not key:
                    continue
                # Remove inline comments that are not quoted
                if " #" in value and not (value.startswith("\"") or value.startswith("'")):
                    value = value.split(" #", 1)[0].strip()
                if (value.startswith("\"") and value.endswith("\"")) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                os.environ.setdefault(key, value)
        return True
    except OSError:
        return False


def load_env_from_candidates() -> None:
    """Load environment variables from common .env locations."""
    candidates = []
    env_file = os.getenv("ENV_FILE")
    if env_file:
        candidates.append(Path(env_file))

    script_dir = Path(__file__).resolve().parent
    candidates.append(Path.cwd() / ".env")
    candidates.append(script_dir / ".env")

    seen = set()
    for candidate in candidates:
        if not candidate:
            continue
        # Deduplicate while preserving order
        key = candidate.resolve() if candidate.exists() else candidate
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            _load_env_file(candidate)


load_env_from_candidates()

# ----- App State -----
if "bots" not in st.session_state:
    st.session_state["bots"] = {}  # symbol -> Bot instance

init_db()

# ----- Restore Running Bots -----
def restore_bots():
    """Restaure les bots depuis la base de données au démarrage."""
    running_bots = fetch_running_bots()

    for bot_data in running_bots:
        symbol = bot_data["symbol"]

        # Vérifier si le bot existe déjà dans la session et s'il est vivant
        if symbol in st.session_state["bots"] and st.session_state["bots"][symbol].is_alive():
            continue

        # Recréer le bot
        try:
            bot = Bot(
                symbol=symbol,
                interval=bot_data["interval"],
                risk_pct=bot_data["risk_pct"],
                max_pos=bot_data["max_pos"],
                testnet=bool(bot_data["testnet"]),
                dry_run=bool(bot_data["dry_run"]),
                api_key=bot_data["api_key"],
                api_secret=bot_data["api_secret"]
            )
            bot.start()
            st.session_state["bots"][symbol] = bot
        except Exception as e:
            # Si on ne peut pas restaurer le bot, on le supprime de la DB
            remove_running_bot(symbol)

# Nettoyer les bots morts de la session
def cleanup_dead_bots():
    """Supprime les bots qui ne sont plus en cours d'exécution de la session state."""
    dead_bots = []
    for symbol, bot in st.session_state["bots"].items():
        if not bot.is_alive():
            dead_bots.append(symbol)

    for symbol in dead_bots:
        del st.session_state["bots"][symbol]
        remove_running_bot(symbol)

if "restored" not in st.session_state:
    restore_bots()
    st.session_state["restored"] = True

cleanup_dead_bots()

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
            # Sauvegarder dans la DB pour persistance
            save_running_bot(symbol, interval, risk_pct, max_pos, testnet, dry_run, api_key, api_sec)
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
            remove_running_bot(sym)
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
                # Mettre à jour dans la DB
                save_running_bot(sym, bot.interval, bot.risk_pct, bot.max_pos, True, True, bot.api_key, bot.api_secret)
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
                # Mettre à jour dans la DB
                save_running_bot(sym, bot.interval, bot.risk_pct, bot.max_pos, False, False, bot.api_key, bot.api_secret)
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

# ---- Tabs for TEST, PROD and REALTIME ----
st.divider()
st.header("📊 Analyse de Performance")

tab_test, tab_prod, tab_realtime = st.tabs(["🔬 TEST (Backtest)", "📈 PROD (Trading Réel)", "📡 SUIVI TEMPS RÉEL"])

# ---- TEST TAB: Backtesting Section ----
with tab_test:
    st.subheader("🔬 Backtesting - Simulation sur Graphiques de Production")
    st.markdown("""
    **Testez votre stratégie sans risquer d'argent réel !**

    Le backtest simule votre stratégie 3 Swings sur des données historiques et affiche les résultats
    sur les **mêmes graphiques que vous verriez en production**. Cela vous permet de :
    - ✅ Visualiser le résultat "réel" de votre stratégie appliquée sans dépenser d'argent
    - ✅ Comparer les résultats simulés avec vos trades de production réels (onglet PROD)
    - ✅ Valider votre stratégie avant de la déployer en mode production

    Les graphiques interactifs montrent les chandeliers, les points d'entrée/sortie, et le P&L cumulé
    exactement comme vous les verriez en trading réel.

    ℹ️ **Note importante :** Les données historiques sont **toujours récupérées depuis l'API Binance de production**
    pour garantir que vous testez sur des données réelles de marché, peu importe votre mode testnet/production.
    """)

    with st.expander("⚙️ Configuration du Backtest", expanded=True):
        bt_col1, bt_col2 = st.columns(2)

        with bt_col1:
            bt_symbol = st.text_input("Symbole pour backtest", "BTCUSDT", key="bt_symbol")
            bt_interval = st.selectbox("Intervalle", ["1m","3m","5m","15m","30m","1h","4h","1d"], index=4, key="bt_interval")
            bt_days = st.slider("Période (jours)", min_value=1, max_value=90, value=30)

        with bt_col2:
            bt_allocation_pct = st.slider("Allocation par trade (% du capital disponible)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
            bt_capital = st.number_input("Capital initial (USDT)", min_value=100.0, value=10000.0, step=100.0)

        # Date range calculation
        end_date = datetime.now()
        start_date = end_date - timedelta(days=bt_days)

        st.info(f"📅 Période de test: {start_date.strftime('%Y-%m-%d %H:%M')} → {end_date.strftime('%Y-%m-%d %H:%M')}")

        run_backtest = st.button("🚀 Lancer la Simulation", type="primary", use_container_width=True)

    if run_backtest:
        with st.spinner("⏳ Téléchargement des données et exécution du backtest..."):
            try:
                # Run backtest asynchronously
                results = asyncio.run(run_backtest_async(
                    symbol=bt_symbol,
                    interval=bt_interval,
                    start_date=start_date,
                    end_date=end_date,
                    allocation_pct=bt_allocation_pct,
                    initial_capital=bt_capital,
                    testnet=default_testnet,
                    api_key=api_key,
                    api_secret=api_sec
                ))

                # Store results in session state
                st.session_state['backtest_results'] = results
                st.success("✅ Simulation terminée avec succès!")

            except Exception as e:
                st.error(f"❌ Erreur lors du backtest: {str(e)}")
                st.exception(e)

    # Display backtest results if available
    if 'backtest_results' in st.session_state:
        results = st.session_state['backtest_results']

        st.divider()
        st.subheader("📊 Résultats de la Simulation")

        # Display statistics summary
        st.markdown(create_statistics_summary(results['statistics']))

        # Display interactive chart
        st.divider()
        st.subheader("📈 Graphique Interactif")
        st.info("💡 **Astuce de Zoom :**\n"
                "- Le graphique ajuste automatiquement l'échelle pour éviter que les valeurs extrêmes ne rendent le reste illisible\n"
                "- Cliquez et glissez sur le graphique pour zoomer sur une zone spécifique\n"
                "- Double-cliquez n'importe où pour réinitialiser le zoom et voir toutes les données\n"
                "- Utilisez les boutons de la barre d'outils (en haut à droite) pour contrôler le zoom")
        fig = create_backtest_chart(results)

        # Configure Plotly chart with toolbar options for better zoom control
        plotly_config = {
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'toImageButtonOptions': {
                'format': 'png',
                'filename': f'backtest_{bt_symbol}',
                'height': 800,
                'width': 1400,
                'scale': 2
            }
        }

        st.plotly_chart(fig, use_container_width=True, config=plotly_config)

        # Display trades table
        st.divider()
        st.subheader("📝 Détail des Trades")

        trades_df = create_trades_dataframe(results['trades'])
        if not trades_df.empty:
            # Add filters
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                filter_type = st.multiselect(
                    "Filtrer par type",
                    options=["BUY", "SELL"],
                    default=["BUY", "SELL"]
                )

            # Apply filters
            if filter_type:
                mask = trades_df['Type'].isin(filter_type) if 'Type' in trades_df.columns else [True] * len(trades_df)
                filtered_df = trades_df[mask]
            else:
                filtered_df = trades_df

            st.dataframe(filtered_df, use_container_width=True, height=400)

            # Download button
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="💾 Télécharger les trades (CSV)",
                data=csv,
                file_name=f"backtest_{bt_symbol}_{start_date.strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Aucun trade exécuté durant la simulation.")

        # Clear results button
        if st.button("🗑️ Effacer les résultats"):
            del st.session_state['backtest_results']
            st.rerun()

# ---- PROD TAB: Production Charts Section ----
with tab_prod:
    st.subheader("📊 Graphiques de Production - Trades Réels")
    st.markdown("""
    Visualisez vos trades de production réels avec les mêmes graphiques interactifs que le backtest.
    Cela vous permet de comparer les résultats simulés avec les résultats réels de votre bot.
    """)

    with st.expander("⚙️ Configuration de la Visualisation de Production", expanded=True):
        prod_col1, prod_col2 = st.columns(2)

        with prod_col1:
            # Get available symbols from trades
            all_prod_trades = fetch_trades(limit=10000)
            prod_symbols = sorted(list({t["symbol"] for t in all_prod_trades})) if all_prod_trades else []

            if prod_symbols:
                prod_symbol = st.selectbox("Symbole", prod_symbols, key="prod_symbol")
                prod_interval = st.selectbox(
                    "Intervalle (pour données de prix)",
                    ["1m","3m","5m","15m","30m","1h","4h","1d"],
                    index=4,
                    key="prod_interval"
                )
            else:
                st.info("Aucun trade de production trouvé dans la base de données.")
                prod_symbol = None

        with prod_col2:
            if prod_symbol:
                # Get date range from trades
                symbol_trades = [t for t in all_prod_trades if t["symbol"] == prod_symbol]
                if symbol_trades:
                    dates = [datetime.fromisoformat(t["ts"]) for t in symbol_trades]
                    min_date = min(dates)
                    max_date = max(dates)

                    # Add some margin
                    chart_start = min_date - timedelta(hours=24)
                    chart_end = max_date + timedelta(hours=24)

                    st.info(f"📅 Période couverte: {min_date.strftime('%Y-%m-%d %H:%M')} → {max_date.strftime('%Y-%m-%d %H:%M')}")
                    st.info(f"💰 Nombre de trades: {len(symbol_trades)}")

        if prod_symbol:
            load_production = st.button("📈 Charger les Graphiques de Production", type="primary", use_container_width=True)
        else:
            load_production = False

    if prod_symbol and load_production:
        with st.spinner("⏳ Chargement des données de production..."):
            try:
                # Fetch production trades for this symbol
                symbol_trades = [t for t in all_prod_trades if t["symbol"] == prod_symbol]

                if not symbol_trades:
                    st.warning("Aucun trade trouvé pour ce symbole.")
                else:
                    # Get date range
                    dates = [datetime.fromisoformat(t["ts"]) for t in symbol_trades]
                    chart_start = min(dates) - timedelta(hours=24)
                    chart_end = max(dates) + timedelta(hours=24)

                    # Fetch historical price data from Binance
                    from binance import AsyncClient

                    async def fetch_prod_data():
                        # ALWAYS use production API for real historical price data
                        client = await AsyncClient.create(
                            api_key=api_key,
                            api_secret=api_sec,
                            testnet=False  # Force production for real market data
                        )
                        try:
                            start_ms = int(chart_start.timestamp() * 1000)
                            end_ms = int(chart_end.timestamp() * 1000)

                            klines = await client.get_historical_klines(
                                prod_symbol,
                                prod_interval,
                                start_ms,
                                end_ms
                            )

                            # Convert to our format
                            candles = []
                            for k in klines:
                                candle = {
                                    'timestamp': int(k[0]),
                                    'open': float(k[1]),
                                    'high': float(k[2]),
                                    'low': float(k[3]),
                                    'close': float(k[4]),
                                    'volume': float(k[5]),
                                }
                                candles.append(candle)

                            return candles
                        finally:
                            await client.close_connection()

                    price_data = asyncio.run(fetch_prod_data())

                    # Store in session state
                    st.session_state['production_data'] = {
                        'price_data': price_data,
                        'trades': symbol_trades,
                        'symbol': prod_symbol
                    }

                    st.success("✅ Données de production chargées avec succès!")

            except Exception as e:
                st.error(f"❌ Erreur lors du chargement: {str(e)}")
                st.exception(e)

    # Display production chart if available
    if 'production_data' in st.session_state:
        prod_data = st.session_state['production_data']

        st.divider()
        st.subheader(f"📊 Graphiques de Production - {prod_data['symbol']}")

        # Create and display chart
        fig = create_production_chart(
            prod_data['price_data'],
            prod_data['trades'],
            title=f"Trading en Production - {prod_data['symbol']}"
        )

        plotly_config = {
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'toImageButtonOptions': {
                'format': 'png',
                'filename': f'production_{prod_data["symbol"]}',
                'height': 800,
                'width': 1400,
                'scale': 2
            }
        }

        st.plotly_chart(fig, use_container_width=True, config=plotly_config)

        # Display statistics
        st.divider()
        st.subheader("📊 Statistiques de Production")

        trades = prod_data['trades']
        sell_trades = [t for t in trades if t['side'] == 'SELL' and t.get('pnl') is not None]

        if sell_trades:
            total_pnl = sum(t['pnl'] for t in sell_trades)
            wins = [t for t in sell_trades if t['pnl'] > 0]
            losses = [t for t in sell_trades if t['pnl'] <= 0]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Trades Fermés", len(sell_trades))
            col2.metric("Win Rate", f"{len(wins)/len(sell_trades)*100:.1f}%")
            col3.metric("P&L Total", f"${total_pnl:.2f}", delta=f"{total_pnl:.2f}")
            col4.metric("Avg P&L", f"${total_pnl/len(sell_trades):.2f}")

            # Trades table
            st.divider()
            st.subheader("📝 Détail des Trades de Production")
            trades_df = create_trades_dataframe(trades)
            st.dataframe(trades_df, use_container_width=True, height=400)
        else:
            st.info("Aucun trade fermé (SELL) avec P&L pour ce symbole.")

        # Clear button
        if st.button("🗑️ Effacer les graphiques de production"):
            del st.session_state['production_data']
            st.rerun()

# ---- REALTIME TAB: Live Bot Monitoring ----
with tab_realtime:
    st.subheader("📡 Suivi des Bots en Temps Réel")
    st.markdown("""
    **Visualisez l'activité de vos bots en temps réel !**

    Cette section affiche pour chaque bot actif :
    - 📊 **Graphique en chandelier** avec les prix en temps réel
    - 📈 **Indicateurs techniques** : EMA courte/longue, RSI, ADX/DMI
    - 🎯 **Signaux de trading** : Points d'entrée (BUY) et de sortie (SELL)
    - 💰 **Position actuelle** : Prix d'entrée, prix actuel, P&L non réalisé
    - ⏱️ **Rafraîchissement automatique** : Les données se mettent à jour automatiquement

    💡 **Astuce** : Vous pouvez zoomer sur les graphiques en cliquant-glissant, et double-cliquer pour réinitialiser.
    """)

    # Configuration de l'auto-refresh
    with st.expander("⚙️ Configuration de l'Affichage", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            auto_refresh = st.checkbox("🔄 Rafraîchissement automatique", value=True)
            if auto_refresh:
                refresh_interval = st.slider(
                    "Intervalle de rafraîchissement (secondes)",
                    min_value=5,
                    max_value=60,
                    value=10,
                    step=5
                )

        with col2:
            show_indicators = st.checkbox("📊 Afficher les indicateurs", value=True)
            show_pnl = st.checkbox("💰 Afficher le P&L", value=True)

    # Récupération des bots actifs
    active_bots = {sym: bot for sym, bot in st.session_state["bots"].items() if bot.is_alive()}

    if not active_bots:
        st.info("🤖 Aucun bot actif pour le moment. Lancez un bot depuis la barre latérale pour commencer !")
    else:
        st.success(f"✅ {len(active_bots)} bot(s) actif(s) détecté(s)")

        # Sélection du bot à afficher (ou tous)
        bot_symbols = ["Tous les bots"] + list(active_bots.keys())
        selected_bot = st.selectbox(
            "Sélectionner un bot à afficher",
            options=bot_symbols,
            key="realtime_bot_selector"
        )

        # Bouton de rafraîchissement manuel
        col_refresh1, col_refresh2, col_refresh3 = st.columns([1, 1, 4])
        with col_refresh1:
            manual_refresh = st.button("🔄 Rafraîchir Maintenant", type="primary")
        with col_refresh2:
            if st.button("⏸️ Arrêter Auto-Refresh"):
                auto_refresh = False

        st.divider()

        # Affichage des graphiques
        if selected_bot == "Tous les bots":
            # Afficher tous les bots
            for symbol, bot in active_bots.items():
                with st.container():
                    st.subheader(f"📊 {symbol}")

                    # Informations du bot
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Statut", "🟢 En cours")
                    col2.metric("Intervalle", bot.interval)
                    col3.metric("Position", bot.pos_side)

                    if bot.pos_side == "LONG" and hasattr(bot, 'entry_price'):
                        # Note: Le P&L précis sera calculé avec le prix actuel du graphique
                        col4.metric("P&L Non Réalisé", "Voir graphique")
                    else:
                        col4.metric("P&L Non Réalisé", "N/A")

                    # Chargement des données
                    try:
                        with st.spinner(f"⏳ Chargement des données pour {symbol}..."):
                            data = get_bot_realtime_data(
                                symbol=symbol,
                                interval=bot.interval,
                                api_key=bot.api_key,
                                api_secret=bot.api_secret,
                                testnet=bot.testnet
                            )

                            # Mise à jour du prix actuel dans la position si elle existe
                            if data['candles'] and data['position']:
                                data['position']['current_price'] = data['candles'][-1]['close']

                            # Création du graphique
                            fig = create_realtime_chart(
                                candles=data['candles'],
                                symbol=symbol,
                                interval=bot.interval,
                                bot_position=data['position'],
                                recent_trades=data['trades']
                            )

                            # Configuration du graphique
                            plotly_config = {
                                'displayModeBar': True,
                                'displaylogo': False,
                                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                                'toImageButtonOptions': {
                                    'format': 'png',
                                    'filename': f'realtime_{symbol}',
                                    'height': 1000,
                                    'width': 1600,
                                    'scale': 2
                                }
                            }

                            st.plotly_chart(fig, use_container_width=True, config=plotly_config)

                            # Affichage des statistiques
                            if data['trades']:
                                sell_trades = [t for t in data['trades'] if t['side'] == 'SELL' and t.get('pnl') is not None]
                                if sell_trades:
                                    st.markdown("**📊 Statistiques (dernières 24h)**")
                                    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

                                    total_pnl = sum(t['pnl'] for t in sell_trades)
                                    wins = len([t for t in sell_trades if t['pnl'] > 0])
                                    losses = len([t for t in sell_trades if t['pnl'] <= 0])
                                    win_rate = (wins / len(sell_trades) * 100) if sell_trades else 0

                                    stat_col1.metric("Trades Fermés", len(sell_trades))
                                    stat_col2.metric("Win Rate", f"{win_rate:.1f}%")
                                    stat_col3.metric("P&L Total", f"{total_pnl:.2f} USDT", delta=f"{total_pnl:.2f}")
                                    stat_col4.metric("P&L Moyen", f"{total_pnl/len(sell_trades):.2f} USDT")

                    except Exception as e:
                        st.error(f"❌ Erreur lors du chargement des données pour {symbol}: {str(e)}")
                        st.exception(e)

                    st.divider()

        else:
            # Afficher un seul bot sélectionné
            symbol = selected_bot
            bot = active_bots[symbol]

            # Informations du bot
            st.subheader(f"Détails du Bot - {symbol}")
            info_col1, info_col2, info_col3, info_col4, info_col5 = st.columns(5)

            info_col1.metric("Statut", "🟢 En cours")
            info_col2.metric("Intervalle", bot.interval)
            info_col3.metric("Position", bot.pos_side)
            info_col4.metric("Risque", f"{bot.risk_pct*100:.1f}%")
            info_col5.metric("Mode", "TESTNET" if bot.testnet else "PRODUCTION")

            if bot.pos_side == "LONG":
                position_info_col1, position_info_col2, position_info_col3 = st.columns(3)
                position_info_col1.metric("Quantité", f"{bot.pos_qty:.8f}")
                position_info_col2.metric("Prix d'Entrée", f"{bot.entry_price:.4f} USDT")

                # Calculer le P&L non réalisé si on a le prix actuel
                try:
                    data_quick = get_bot_realtime_data(
                        symbol=symbol,
                        interval=bot.interval,
                        api_key=bot.api_key,
                        api_secret=bot.api_secret,
                        testnet=bot.testnet
                    )
                    if data_quick['candles']:
                        current_price = data_quick['candles'][-1]['close']
                        pnl_unrealized = (current_price - bot.entry_price) * bot.pos_qty
                        position_info_col3.metric("P&L Non Réalisé", f"{pnl_unrealized:.2f} USDT", delta=f"{pnl_unrealized:.2f}")
                except:
                    position_info_col3.metric("P&L Non Réalisé", "Calcul en cours...")

            st.divider()

            # Chargement et affichage du graphique
            try:
                with st.spinner(f"⏳ Chargement des données pour {symbol}..."):
                    data = get_bot_realtime_data(
                        symbol=symbol,
                        interval=bot.interval,
                        api_key=bot.api_key,
                        api_secret=bot.api_secret,
                        testnet=bot.testnet
                    )

                    # Mise à jour du prix actuel dans la position si elle existe
                    if data['candles'] and data['position']:
                        data['position']['current_price'] = data['candles'][-1]['close']

                    # Création du graphique
                    fig = create_realtime_chart(
                        candles=data['candles'],
                        symbol=symbol,
                        interval=bot.interval,
                        bot_position=data['position'],
                        recent_trades=data['trades']
                    )

                    # Configuration du graphique
                    plotly_config = {
                        'displayModeBar': True,
                        'displaylogo': False,
                        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
                        'toImageButtonOptions': {
                            'format': 'png',
                            'filename': f'realtime_{symbol}',
                            'height': 1000,
                            'width': 1600,
                            'scale': 2
                        }
                    }

                    st.plotly_chart(fig, use_container_width=True, config=plotly_config)

                    # Affichage des statistiques détaillées
                    st.divider()
                    st.subheader("📊 Statistiques de Trading (dernières 24h)")

                    if data['trades']:
                        sell_trades = [t for t in data['trades'] if t['side'] == 'SELL' and t.get('pnl') is not None]

                        if sell_trades:
                            total_pnl = sum(t['pnl'] for t in sell_trades)
                            wins = [t for t in sell_trades if t['pnl'] > 0]
                            losses = [t for t in sell_trades if t['pnl'] <= 0]
                            win_rate = (len(wins) / len(sell_trades) * 100) if sell_trades else 0

                            stat_col1, stat_col2, stat_col3, stat_col4, stat_col5 = st.columns(5)
                            stat_col1.metric("Total Trades", len(data['trades']))
                            stat_col2.metric("Trades Fermés", len(sell_trades))
                            stat_col3.metric("Win Rate", f"{win_rate:.1f}%")
                            stat_col4.metric("P&L Total", f"{total_pnl:.2f} USDT", delta=f"{total_pnl:.2f}")
                            stat_col5.metric("P&L Moyen", f"{total_pnl/len(sell_trades):.2f} USDT")

                            # Tableau des trades récents
                            st.divider()
                            st.subheader("📝 Trades Récents (24h)")
                            trades_df = create_trades_dataframe(data['trades'])
                            st.dataframe(trades_df, use_container_width=True, height=300)
                        else:
                            st.info("Aucun trade fermé dans les dernières 24h")
                    else:
                        st.info("Aucun trade enregistré dans les dernières 24h")

            except Exception as e:
                st.error(f"❌ Erreur lors du chargement des données: {str(e)}")
                st.exception(e)

        # Auto-refresh si activé
        if auto_refresh:
            # Initialiser le dernier temps de refresh
            if 'last_refresh_time' not in st.session_state:
                st.session_state['last_refresh_time'] = time.time()

            # Vérifier si l'intervalle est écoulé
            current_time = time.time()
            time_elapsed = current_time - st.session_state['last_refresh_time']

            if time_elapsed >= refresh_interval or manual_refresh:
                st.session_state['last_refresh_time'] = current_time
                st.rerun()
            else:
                # Afficher un compteur
                time_remaining = int(refresh_interval - time_elapsed)
                st.info(f"🔄 Prochain rafraîchissement dans {time_remaining} secondes...")

                # Forcer un rerun après 1 seconde pour mettre à jour le compteur
                time.sleep(1)
                st.rerun()

st.caption(f"DB: {DB_PATH}")
