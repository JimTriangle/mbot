# Multi-Bot Binance Spot Dashboard (Streamlit)

Un tableau de bord **Streamlit** pour lancer, arrêter et monitorer plusieurs bots Spot (Binance) basés sur la stratégie *Phases de Tendance (Optimisé+)* (EMA20/50, RSI14, DMI/ADX 14/14).

## Installation

```bash
pip install -r requirements.txt
```

## Variables d'environnement (à définir avant de lancer)

```bash
export BINANCE_API_KEY="XXX"
export BINANCE_API_SECRET="YYY"
export TESTNET="true"      # "false" pour réel (⚠️)
export DRY_RUN="true"      # "false" pour envoyer des ordres
```

> Tu peux aussi renseigner ces clés dans le panneau **Secrets** de Streamlit Cloud ou via un fichier `.env` (à gérer toi-même).

## Lancer le dashboard

```bash
streamlit run dashboard.py
```

## Fonctionnalités

- Lancer **plusieurs bots** (une paire = un bot) en parallèle.
- Monitoring en direct : statut, positions, PnL réalisé, nombre de trades, win rate, notional cumulé.
- Graphiques des performances et journal en direct par bot.
- Persistance en **SQLite** (fichier `mbot.db`).
- **Testnet** par défaut + **DRY_RUN** pour tester sans risque.

## Avertissements

- Ceci est un exemple éducatif. **Testnet** d'abord, auditez le code et **assumez vos risques**.
- Spot uniquement (long-only). Pas de marge/futures ici.
- Les stratégies de risk management (SL/TP, OCO) sont minimales et optionnelles.
