# Architecture du Dashboard Multi-Bots

## Vue d'ensemble

Le projet est conçu avec une architecture modulaire permettant de gérer plusieurs bots de trading en parallèle via un dashboard centralisé, tout en conservant la possibilité de lancer des bots autonomes.

```
┌─────────────────────────────────────────────────────────────┐
│                    DASHBOARD (Streamlit)                    │
│                      dashboard.py                           │
│  - Interface graphique                                      │
│  - Gestion multi-bots                                       │
│  - Visualisation des performances                           │
└────────────┬────────────────────────────────┬───────────────┘
             │                                │
             ▼                                ▼
    ┌────────────────┐              ┌─────────────────┐
    │   bot_core.py  │              │   storage.py    │
    │                │              │                 │
    │ - Classe Bot   │◄────────────►│ - init_db()     │
    │ - Strategy     │   écrit dans │ - insert_*()    │
    │ - Trading      │              │ - fetch_*()     │
    └────────┬───────┘              └────────┬────────┘
             │                               │
             ▼                               ▼
    ┌─────────────────┐            ┌──────────────────┐
    │ Binance API     │            │  bot_data.db     │
    │ (python-binance)│            │    (SQLite)      │
    └─────────────────┘            └──────────────────┘


    ┌──────────────────────────────────┐
    │   spot_btcusd.py (LEGACY)        │
    │                                  │
    │ - Ancienne version autonome      │
    │ - Stratégie 3 swings (deprecated)│
    │ - Utilisé pour référence         │
    └──────────────────────────────────┘
```

## Composants

### 1. `dashboard.py` - Interface Streamlit

**Rôle** : Interface graphique pour gérer tous les bots

**Fonctionnalités** :
- Création de bots pour différentes paires (BTCUSDT, ETHUSDT, etc.)
- Configuration par bot (testnet/prod, dry_run)
- Affichage des positions en temps réel
- Graphiques de PnL
- Logs centralisés
- Start/Stop des bots

**Connexions** :
- Importe `Bot` depuis `bot_core.py`
- Importe `init_db`, `fetch_trades`, `fetch_positions`, `fetch_logs` depuis `storage.py`
- Stocke les instances de Bot dans `st.session_state["bots"]`

### 2. `bot_core.py` - Logique réutilisable

**Rôle** : Contient la logique du bot modulaire et thread-safe

**Classes** :

#### `TrendPhaseStrategy`
- Calcul d'indicateurs techniques (EMA, RSI, ADX/DMI)
- Détection de phases de tendance forte (haussière/baissière)
- Génération de signaux BUY/SELL basés sur les changements de tendance
- Inspirée du Pine Script "Phases de Tendance (Optimisé+)"

#### `Bot`
- Gère un bot pour une paire spécifique
- Tourne dans son propre thread
- Utilise `TrendPhaseStrategy`
- Écoute les websockets Binance
- Exécute les trades (ou simule en dry_run)

**Connexions** :
- Utilise `python-binance` pour l'API Binance
- Écrit dans la DB via `storage.py` :
  - `insert_trade()` : Enregistre chaque trade
  - `update_position()` : Met à jour la position actuelle
  - `clear_position()` : Supprime la position (FLAT)
  - `insert_log()` : Écrit les logs

### 3. `storage.py` - Gestion de la base de données

**Rôle** : Abstraction de la base de données SQLite

**Tables** :

#### `trades`
- `id`, `symbol`, `side`, `qty`, `price`, `quote_qty`, `pnl`, `ts`, `order_id`, `entry_price`, `notes`
- Stocke l'historique de tous les trades (BUY/SELL)

#### `positions`
- `symbol`, `side`, `qty`, `entry_price`, `current_price`, `pnl_unrealized`, `last_update`
- Stocke les positions ouvertes actuelles

#### `logs`
- `id`, `symbol`, `level`, `message`, `ts`
- Stocke tous les logs de tous les bots

**Fonctions** :
- `init_db()` : Crée les tables si elles n'existent pas
- `insert_trade()` : Enregistre un trade
- `update_position()` : Met à jour une position
- `clear_position()` : Supprime une position
- `insert_log()` : Enregistre un log
- `fetch_trades()` : Récupère l'historique des trades
- `fetch_positions()` : Récupère les positions actuelles
- `fetch_logs()` : Récupère les logs

### 4. `spot_btcusd.py` - Bot autonome

**Rôle** : Bot standalone pour BTCUSDT (non modifié)

**Caractéristiques** :
- Fonctionne indépendamment du dashboard
- Contient sa propre implémentation de `ThreeSwingsStrategy`
- Utilisé pour tests et développement
- **N'écrit PAS dans la base de données** (logs uniquement en console)

**Utilisation** :
```bash
python spot_btcusd.py
```

## Flux de données

### 1. Lancement d'un bot via le dashboard

```
User (dashboard.py)
  │
  ├─► Saisit : symbol="ETHUSDT", interval="1m", risk_pct=0.1
  │
  ├─► Clique "Lancer le bot"
  │
  └─► dashboard.py crée :
        bot = Bot(symbol="ETHUSDT", interval="1m", ...)
        bot.start()
        st.session_state["bots"]["ETHUSDT"] = bot
```

### 2. Exécution du bot

```
Bot thread (bot_core.py)
  │
  ├─► Connexion à Binance API
  │
  ├─► Récupération historique (200 bougies)
  │     └─► Initialisation de ThreeSwingsStrategy
  │
  ├─► Écoute websocket klines
  │     │
  │     ├─► Sur chaque tick : check_breakout()
  │     │     └─► Si signal → _execute_signal()
  │     │           └─► insert_trade() dans storage.py
  │     │
  │     └─► Sur bougie fermée :
  │           ├─► add_candle()
  │           ├─► update_pivots()
  │           ├─► analyze_structure()
  │           └─► update_breakout_levels()
  │
  └─► Boucle jusqu'à bot.stop()
```

### 3. Visualisation dans le dashboard

```
Dashboard (streamlit auto-refresh)
  │
  ├─► Pour chaque bot dans session_state["bots"] :
  │     ├─► Affiche bot.is_alive() → 🟢/🔴
  │     ├─► Affiche bot.pos_side, bot.pos_qty, bot.entry_price
  │     └─► Boutons Stop/Restart
  │
  ├─► fetch_positions() depuis storage.py
  │     └─► Affiche dans un DataFrame
  │
  ├─► fetch_trades() depuis storage.py
  │     └─► Affiche historique + graphique PnL
  │
  └─► fetch_logs() depuis storage.py
        └─► Affiche logs filtrés par symbole
```

## Stratégie 3 Swings

### Détection des pivots

```
Prix
  │
  │     ╱╲                    Pivot High 3
  │    ╱  ╲       ╱╲          (oldest)
  │   ╱    ╲     ╱  ╲     ╱╲
  │  ╱      ╲   ╱    ╲   ╱  ╲  ← Pivot High 1 (latest)
  │ ╱        ╲ ╱      ╲ ╱    ╲
  │╱          V        V      V
  └─────────────────────────────► Temps
              ▲        ▲      ▲
        Pivot Low 3    │   Pivot Low 1
                  Pivot Low 2
```

### Structure haussière

```
Conditions :
- low1 > low2 > low3
- high1 > high2 > high3

Signal BUY :
- Prix casse high1 + 0.05%
```

### Structure baissière

```
Conditions :
- low1 < low2 < low3
- high1 < high2 < high3

Signal SELL :
- Prix casse low1 - 0.05%
```

## Pourquoi spot_btcusd.py n'a pas été modifié ?

**Objectif** : Ne pas casser le code existant qui fonctionne

**Solution** :
1. On a **extrait** la logique dans `bot_core.py`
2. `spot_btcusd.py` reste **autonome** et **inchangé**
3. Le dashboard utilise `bot_core.py` pour créer des bots
4. Les deux peuvent coexister sans conflit

**Avantages** :
- ✅ `spot_btcusd.py` continue de fonctionner exactement comme avant
- ✅ Possibilité de tester rapidement sur BTCUSDT sans dashboard
- ✅ Code modulaire et réutilisable pour le dashboard
- ✅ Séparation des responsabilités

## Configuration

### Variables d'environnement (.env)

```bash
BINANCE_API_KEY=xxx          # Utilisé par dashboard et spot_btcusd.py
BINANCE_API_SECRET=yyy       # Utilisé par dashboard et spot_btcusd.py
TESTNET=true                 # Utilisé par spot_btcusd.py
DRY_RUN=true                 # Utilisé par spot_btcusd.py
SYMBOL=BTCUSDT               # Utilisé par spot_btcusd.py
```

**Note** : Le dashboard permet de configurer testnet/dry_run **par bot** via l'interface graphique.

## Déploiement

### Local

```bash
# Option 1 : Dashboard multi-bots
streamlit run dashboard.py

# Option 2 : Bot autonome BTCUSDT
python spot_btcusd.py
```

### Production (exemple avec systemd)

```bash
# Bot BTCUSDT en service
sudo systemctl start mbot-btcusd

# Dashboard accessible via nginx
sudo systemctl start mbot-dashboard
```

## Sécurité

- ✅ Clés API dans `.env` (ignoré par git)
- ✅ Mode TESTNET par défaut
- ✅ Mode DRY_RUN par défaut
- ✅ Permissions restreintes sur bot_data.db
- ⚠️ Ne JAMAIS commiter les clés API
- ⚠️ Tester en TESTNET avant PROD

## Maintenance

### Ajouter une nouvelle paire

Via le dashboard :
1. Entrer le symbole (ex: "SOLUSDT")
2. Configurer intervalle, risque
3. Cliquer "Lancer le bot"

### Consulter la base de données

```bash
sqlite3 bot_data.db
.tables
SELECT * FROM trades WHERE symbol='BTCUSDT';
SELECT * FROM positions;
SELECT * FROM logs ORDER BY ts DESC LIMIT 10;
```

### Réinitialiser la DB

```bash
rm bot_data.db
# Au prochain lancement, la DB sera recréée vide
```

## Améliorations futures possibles

1. **Graphiques en temps réel** : Ajouter des charts avec les pivots visualisés
2. **Backtesting** : Module de test sur données historiques
3. **Alertes** : Notifications Telegram/Discord sur signaux
4. **API REST** : Exposer les données via FastAPI
5. **WebSockets dashboard** : Mise à jour en temps réel sans refresh
6. **Multi-stratégies** : Permettre de choisir différentes stratégies
7. **Risk management** : Stop-loss, take-profit, trailing stop
8. **Portfolio management** : Gestion globale du capital
