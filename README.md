# Multi-Bot Binance Spot Dashboard (Streamlit)

Un tableau de bord **Streamlit** pour lancer, arrêter et monitorer plusieurs bots Spot (Binance) basés sur la stratégie **3 Swings avec détection de breakout**.

## Architecture

Le projet comprend :

- **`spot_btcusd.py`** : Bot autonome BTCUSDT avec stratégie 3 swings (peut fonctionner indépendamment)
- **`dashboard.py`** : Interface Streamlit pour gérer plusieurs bots en parallèle
- **`bot_core.py`** : Classe Bot réutilisable avec la stratégie 3 swings
- **`storage.py`** : Gestion de la base de données SQLite (trades, positions, logs)
- **`bot_data.db`** : Base de données créée automatiquement pour stocker l'historique

## Stratégie 3 Swings

La stratégie détecte des structures de marché basées sur 3 pivots (hauts et bas) :
- **Structure haussière** : Pivots bas et hauts croissants → Signal BUY au breakout du dernier pivot haut
- **Structure baissière** : Pivots bas et hauts décroissants → Signal SELL au breakout du dernier pivot bas
- **Confirmation** : Possibilité de confirmer sur timeframe supérieur (ex: 1m confirmé par 15m)
- **Détection en temps réel** : Les breakouts sont détectés sur chaque tick de prix

## Installation

1. Cloner le dépôt
2. Créer un fichier `.env` à partir de `.env.example` :

```bash
cp .env.example .env
```

3. Éditer `.env` et ajouter vos clés API Binance

4. Installer les dépendances :

```bash
pip install -r requirements.txt
```

## Configuration (.env)

```bash
# Clés API Binance (obligatoire)
BINANCE_API_KEY=votre_cle_api
BINANCE_API_SECRET=votre_secret_api

# Mode de fonctionnement
TESTNET=true        # true = testnet, false = production (⚠️ argent réel)
DRY_RUN=true        # true = simulation, false = ordres réels (⚠️ argent réel)

# Configuration pour spot_btcusd.py
SYMBOL=BTCUSDT      # Paire de trading
```

## Utilisation

### Option 1 : Dashboard multi-bots (recommandé)

Lance l'interface graphique pour gérer plusieurs bots :

```bash
streamlit run dashboard.py
```

Fonctionnalités du dashboard :
- ✅ Lancer plusieurs bots (différentes paires) en parallèle
- ✅ Suivre les positions en temps réel
- ✅ Voir les graphiques de PnL par bot
- ✅ Consulter l'historique des trades
- ✅ Logs centralisés
- ✅ Basculer entre TESTNET et PRODUCTION par bot
- ✅ Mode DRY_RUN configurable par bot

### Option 2 : Bot autonome BTCUSDT

Lance directement le bot BTCUSDT sans dashboard :

```bash
python spot_btcusd.py
```

Ce mode est utile pour :
- Tester la stratégie sur une seule paire
- Développer et déboguer
- Utilisation en ligne de commande

## Référence API Binance

Le projet utilise la bibliothèque [python-binance](https://github.com/sammchardy/python-binance) de sammchardy.

Documentation complète : https://python-binance.readthedocs.io/

## Avertissements ⚠️

- **ÉDUCATIF UNIQUEMENT** : Ce code est fourni à des fins d'apprentissage
- **TESTEZ D'ABORD** : Utilisez toujours TESTNET=true et DRY_RUN=true pour tester
- **RISQUES FINANCIERS** : Le trading automatisé peut entraîner des pertes importantes
- **AUDITEZ LE CODE** : Comprenez complètement le code avant de l'utiliser avec de l'argent réel
- **PAS DE GARANTIE** : Aucune garantie de profit ou de bon fonctionnement
- **SPOT UNIQUEMENT** : Long-only, pas de marge/futures

## Structure des fichiers

```
mbot/
├── dashboard.py          # Interface Streamlit multi-bots
├── spot_btcusd.py       # Bot autonome BTCUSDT (ne pas modifier)
├── bot_core.py          # Logique réutilisable du bot
├── storage.py           # Gestion base de données SQLite
├── requirements.txt     # Dépendances Python
├── .env.example        # Template de configuration
├── .env                # Configuration (à créer, ignoré par git)
└── bot_data.db         # Base de données (créée automatiquement)
```
