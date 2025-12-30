# Guide de démarrage rapide

## 🚀 Démarrage en 5 minutes

### 1. Installation

```bash
# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copier le fichier de configuration d'exemple
cp .env.example .env

# Éditer .env et ajouter vos clés API Binance
# IMPORTANT: Gardez TESTNET=true et DRY_RUN=true pour commencer !
nano .env
```

**Contenu minimal de `.env` :**
```bash
BINANCE_API_KEY=votre_cle_api_ici
BINANCE_API_SECRET=votre_secret_api_ici
TESTNET=true
DRY_RUN=true
```

### 3. Lancer le dashboard

```bash
streamlit run dashboard.py
```

Le dashboard s'ouvrira dans votre navigateur sur http://localhost:8501

### 4. Créer votre premier bot

Dans le dashboard :

1. **Configurer les clés API** (sidebar gauche)
   - Si vous n'avez pas mis les clés dans `.env`, entrez-les ici

2. **Nouveau bot** (sidebar)
   - Symbole : `BTCUSDT`
   - Intervalle : `1m`
   - Risque : `10%`
   - Mode : `TEST` (recommandé)
   - DRY_RUN : `☑` activé (recommandé)

3. **Cliquer sur "Lancer le bot"**

4. **Observer** :
   - Statut du bot : 🟢 running
   - Logs en temps réel
   - Positions et trades

### 5. Alternative : Bot autonome BTCUSDT

Si vous préférez utiliser le bot en ligne de commande :

```bash
python spot_btcusd.py
```

Sortie attendue :
```
======================================================================
▶ BOT 3 SWINGS - VERSION REALISTE
   Symbole: BTCUSDT
   Timeframe: 1m
   Confirmation: 15m
   Stratégie: BREAKOUT (temps réel)
   Lag pivots: 3 bougies (3 min)
   Mode: TESTNET (DRY-RUN)
======================================================================

✅ Connexion...
✅ Connecté
```

## 📊 Comprendre le dashboard

### Bots actifs

Chaque bot affiche :
- **Symbole** : La paire tradée (ex: BTCUSDT)
- **Statut** : 🟢 running ou 🔴 stopped
- **Position** : LONG qty @ prix ou FLAT
- **Bouton Stop** : Arrêter le bot
- **Boutons TEST/PROD** : Relancer en mode différent

### Graphique PnL

- Sélectionner un symbole pour voir le graphique
- Le PnL cumulé s'affiche au fil des trades fermés
- KPIs : Win rate, nombre de trades gagnants/perdants

### Logs

- Tous les événements de tous les bots
- Filtrable par symbole
- Horodatés et catégorisés (INFO, ERROR, etc.)

## ⚙️ Configuration avancée

### Paramètres de la stratégie

Dans `bot_core.py`, vous pouvez modifier :

```python
# Pivots
PIVOT_LEFT = 3      # Bougies à gauche du pivot
PIVOT_RIGHT = 3     # Bougies à droite du pivot (lag)

# Breakout
BREAKOUT_THRESHOLD = 0.05  # 0.05% au-dessus/en-dessous

# Filtres
MIN_STRUCTURE_STRENGTH = 0.3  # Force minimale de structure
MIN_PIVOT_DISTANCE = 20       # Distance minimale entre pivots

# Confirmation
USE_HIGHER_TIMEFRAME = True   # Confirmer sur timeframe supérieur
HIGHER_TIMEFRAME = "15m"      # Timeframe de confirmation
```

### Passer en PRODUCTION ⚠️

**ATTENTION** : Seulement après avoir testé en TESTNET !

1. Obtenir des clés API pour l'environnement de **production**
2. Modifier `.env` :
   ```bash
   TESTNET=false
   DRY_RUN=false  # Attention : ordres réels !
   ```
3. Dans le dashboard, créer un bot en mode **PROD**
4. **Surveiller attentivement** les premières heures

## 🔍 Vérifier que tout fonctionne

### Test 1 : Base de données

```bash
python -c "from storage import init_db, insert_log, fetch_logs; init_db(); print('✅ DB OK')"
```

### Test 2 : Imports

```bash
python -c "from bot_core import Bot; print('✅ Bot OK')"
```

### Test 3 : Dashboard

```bash
# Lancer le dashboard
streamlit run dashboard.py

# Vérifier dans le navigateur : http://localhost:8501
# Vous devriez voir l'interface sans erreur
```

## 🐛 Problèmes courants

### Erreur : "No module named 'binance'"

```bash
pip install python-binance
```

### Erreur : "No module named 'streamlit'"

```bash
pip install streamlit
```

### Dashboard ne se lance pas

```bash
# Vérifier que streamlit est installé
streamlit --version

# Réinstaller si nécessaire
pip install --upgrade streamlit
```

### Bot ne se connecte pas à Binance

- Vérifier que les clés API sont correctes
- Vérifier que les clés ont les permissions spot
- Si en TESTNET, vérifier que les clés sont bien des clés testnet
- URL testnet : https://testnet.binance.vision/

### Aucun signal généré

C'est normal ! La stratégie 3 swings nécessite :
1. **200 bougies** pour initialiser
2. **3 pivots hauts et 3 pivots bas** détectés
3. Une **structure claire** (haussière ou baissière)
4. Un **breakout** du niveau de prix

Cela peut prendre plusieurs heures avant le premier signal.

## 📚 Ressources

- **Documentation API Binance** : https://python-binance.readthedocs.io/
- **Architecture du projet** : Voir `ARCHITECTURE.md`
- **README complet** : Voir `README.md`

## 🆘 Support

En cas de problème :

1. Consulter `ARCHITECTURE.md` pour comprendre le fonctionnement
2. Vérifier les logs dans le dashboard
3. Tester avec `spot_btcusd.py` en mode debug
4. Consulter la documentation python-binance

## ⚠️ Avertissement final

- Ce code est **éducatif uniquement**
- **Pas de garantie** de profit ou de bon fonctionnement
- Le trading comporte des **risques financiers importants**
- **Testez d'abord** en TESTNET et DRY_RUN
- **Comprenez le code** avant de l'utiliser avec de l'argent réel

**Bon trading responsable ! 🚀📈**
