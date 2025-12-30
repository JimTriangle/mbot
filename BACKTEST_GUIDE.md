# 🔬 Guide d'utilisation du système de backtesting

Ce guide explique comment utiliser le système de backtesting pour tester votre stratégie 3 Swings sur des données historiques.

## 📋 Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Utilisation via le Dashboard](#utilisation-via-le-dashboard)
5. [Utilisation en ligne de commande](#utilisation-en-ligne-de-commande)
6. [Interprétation des résultats](#interprétation-des-résultats)
7. [Exemples](#exemples)

---

## 🎯 Vue d'ensemble

Le système de backtesting vous permet de :

- **Simuler la stratégie** sur des données historiques réelles de Binance
- **Visualiser graphiquement** les points d'achat/vente avec un graphique interactif Plotly
- **Analyser les performances** avec des statistiques détaillées (win rate, P&L, drawdown, etc.)
- **Valider votre stratégie** avant de la déployer en production
- **Identifier les problèmes** potentiels et optimiser les paramètres

### Composants

Le système se compose de 3 fichiers principaux :

1. **`backtest.py`** - Moteur de backtesting qui simule la stratégie
2. **`backtest_viz.py`** - Visualisations graphiques avec Plotly
3. **`dashboard.py`** - Interface Streamlit intégrée

---

## 📦 Installation

### Prérequis

- Python 3.8+
- Compte Binance (Testnet ou Production)
- Clés API Binance

### Installation des dépendances

```bash
pip install -r requirements.txt
```

Les dépendances incluent :
- `streamlit` - Interface web
- `python-binance` - API Binance
- `pandas` - Manipulation de données
- `numpy` - Calculs numériques
- `plotly` - Graphiques interactifs
- `python-dotenv` - Gestion des variables d'environnement

---

## ⚙️ Configuration

### 1. Créer un fichier `.env`

Créez un fichier `.env` à la racine du projet :

```bash
# Clés API Binance
BINANCE_API_KEY=votre_api_key
BINANCE_API_SECRET=votre_api_secret

# Configuration par défaut
TESTNET=true
DRY_RUN=true
```

### 2. Obtenir des clés API Binance

**Testnet (recommandé pour débuter) :**
1. Allez sur https://testnet.binance.vision/
2. Créez un compte et générez des clés API
3. Les fonds sont fictifs - parfait pour tester

**Production :**
1. Connectez-vous à votre compte Binance
2. API Management > Create API
3. ⚠️ **ATTENTION** : Utilisez uniquement en DRY_RUN au début !

---

## 🖥️ Utilisation via le Dashboard

### Lancer le Dashboard

```bash
streamlit run dashboard.py
```

Le dashboard s'ouvre automatiquement dans votre navigateur (généralement http://localhost:8501).

### Configuration du Backtest

1. **Scrollez jusqu'à la section "Backtesting - Simulation Historique"**

2. **Configurez les paramètres :**

   | Paramètre | Description | Valeur recommandée |
   |-----------|-------------|-------------------|
   | **Symbole** | Paire de trading | BTCUSDT, ETHUSDT, etc. |
   | **Intervalle** | Timeframe des bougies | 30m ou 1h (pour débuter) |
   | **Période (jours)** | Nombre de jours à tester | 30 jours |
   | **Risque (%)** | % du capital par trade | 1% (conservateur) |
   | **Position max (USDT)** | Taille max de position | 1000 USDT |
   | **Capital initial (USDT)** | Capital de départ | 10000 USDT |

3. **Cliquez sur "🚀 Lancer la Simulation"**

4. **Attendez** que le système télécharge les données et exécute le backtest (quelques secondes à 1 minute)

### Résultats affichés

#### 📊 Résumé des Performances

Statistiques clés avec interprétation automatique :
- **Trading** : Total d'ordres, achats, ventes, win rate
- **P&L** : Gains/pertes, rendement, capital final
- **Risque** : Max drawdown, profit factor
- **Temps** : Durée moyenne de détention

#### 📈 Graphique Interactif

Graphique Plotly en 2 panneaux :

**Panneau supérieur - Prix et Trades :**
- 🕯️ Chandelier japonais (vert = hausse, rouge = baisse)
- 🟢 Triangles verts vers le haut = Achats
- 🔴 Triangles rouges vers le bas = Ventes
- ⭐ Étoiles roses = Pivots hauts
- ⭐ Étoiles bleues = Pivots bas

**Panneau inférieur - P&L Cumulé :**
- Ligne bleue = Évolution du P&L au fil du temps
- Zone verte/rouge = Gains/pertes

**Fonctionnalités interactives :**
- Zoom : Cliquez-glissez sur le graphique
- Pan : Shift + cliquez-glissez
- Hover : Survolez pour voir les détails
- Reset : Double-clic pour réinitialiser

#### 📝 Détail des Trades

Tableau filtrable avec tous les trades :
- Date/Heure exacte
- Type (BUY/SELL)
- Prix d'exécution
- Quantité
- Montant en USDT
- P&L (pour les ventes)
- Durée de détention

**Filtres disponibles :**
- Type de trade (BUY, SELL)

**Export :**
- Bouton "💾 Télécharger les trades (CSV)" pour analyser dans Excel

---

## 💻 Utilisation en ligne de commande

### Script de test rapide

Un script `test_backtest.py` est fourni pour tester rapidement :

```bash
python3 test_backtest.py
```

Ce script :
- Teste le backtest sur BTCUSDT sur 7 jours
- Affiche les résultats dans le terminal
- Permet de vérifier que tout fonctionne

### Utilisation programmatique

Vous pouvez aussi utiliser le module directement dans vos scripts :

```python
import asyncio
from datetime import datetime, timedelta
from backtest import run_backtest_async

async def my_backtest():
    # Configuration
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    # Exécution
    results = await run_backtest_async(
        symbol="BTCUSDT",
        interval="1h",
        start_date=start_date,
        end_date=end_date,
        risk_pct=1.0,
        max_pos=1000.0,
        initial_capital=10000.0,
        testnet=True,
        api_key="votre_key",
        api_secret="votre_secret"
    )

    # Résultats
    print(f"P&L total: ${results['statistics']['total_pnl']:.2f}")
    print(f"Win rate: {results['statistics']['win_rate']:.2f}%")
    print(f"Nombre de trades: {len(results['trades'])}")

# Exécution
asyncio.run(my_backtest())
```

---

## 📊 Interprétation des résultats

### Métriques clés

#### 1. Win Rate (Taux de réussite)

**Formule :** `(Trades gagnants / Total trades) × 100`

- ✅ **≥ 60%** : Excellent
- ✔️ **50-59%** : Bon
- ⚠️ **40-49%** : Moyen - Optimisation recommandée
- ❌ **< 40%** : Faible - Revoir la stratégie

**Note :** Un win rate élevé ne garantit pas la rentabilité. Un win rate de 40% peut être profitable si les gains moyens sont > 2× les pertes moyennes.

#### 2. Profit Factor (Facteur de profit)

**Formule :** `Somme des gains / Somme des pertes`

- ✅ **≥ 2.0** : Excellent - Les gains sont ≥ 2× les pertes
- ✔️ **1.5-1.99** : Bon
- ⚠️ **1.0-1.49** : Rentable mais fragile
- ❌ **< 1.0** : Non rentable - Pertes > Gains

**Interprétation :**
- Profit factor de 2.0 = Pour chaque $1 perdu, vous gagnez $2
- Indispensable d'avoir **> 1.0** pour être rentable

#### 3. Max Drawdown (Perte maximale)

**Définition :** Plus grande baisse du capital depuis un pic

- ✅ **≤ 10%** : Risque très contrôlé
- ⚠️ **10-20%** : Risque modéré
- ❌ **> 20%** : Risque élevé - Peut nécessiter beaucoup de capital

**Importance :** Le drawdown est souvent sous-estimé. Un drawdown de 50% nécessite un gain de 100% pour revenir au capital initial !

#### 4. Rendement (Return %)

**Formule :** `((Capital final - Capital initial) / Capital initial) × 100`

**À relativiser selon :**
- **Durée du backtest** : +10% sur 1 mois ≠ +10% sur 1 an
- **Risque pris** : +50% avec 40% de drawdown n'est pas mieux que +20% avec 5% de drawdown

**Annualisation approximative :**
```
Rendement annualisé ≈ (Rendement / Jours) × 365
```

Exemple : +15% sur 30 jours ≈ 182% annualisé (théorique, rarement réalisable)

### Signaux d'alerte 🚨

**Mauvaise stratégie :**
- Win rate < 40%
- Profit factor < 1.0
- Rendement négatif
- Très peu de trades (< 5 sur 30 jours)

**Stratégie trop agressive :**
- Max drawdown > 30%
- Gains et pertes très volatils
- Trades très fréquents (> 50 par jour sur 1h)

**Overfitting (sur-optimisation) :**
- Résultats parfaits (win rate > 90%)
- Très peu de pertes
- ⚠️ Risque de ne pas fonctionner en production

### Comparaison avec un benchmark

Comparez toujours vos résultats avec le **Buy & Hold** :

**Exemple sur 30 jours :**
- Stratégie : +12%
- Buy & Hold BTC : +8%
- ✅ Stratégie meilleure de +4%

Mais aussi :
- Drawdown stratégie : 15%
- Drawdown BTC : 20%
- ✅ Moins de risque pour plus de gain !

---

## 💡 Exemples

### Exemple 1 : Test conservateur sur BTC

**Objectif :** Tester la stratégie avec peu de risque

```
Symbole: BTCUSDT
Intervalle: 1h
Période: 30 jours
Risque: 0.5%
Position max: 500 USDT
Capital initial: 10000 USDT
```

**Résultats attendus :**
- Peu de trades (5-15)
- Drawdown faible (< 5%)
- Rendement modeste (0-5%)

### Exemple 2 : Test agressif sur ETH

**Objectif :** Maximiser les opportunités

```
Symbole: ETHUSDT
Intervalle: 15m
Période: 14 jours
Risque: 2%
Position max: 2000 USDT
Capital initial: 10000 USDT
```

**Résultats attendus :**
- Beaucoup de trades (20-50)
- Drawdown moyen (5-15%)
- Rendement variable (-10% à +20%)

### Exemple 3 : Comparaison multi-intervalles

**Objectif :** Trouver le meilleur timeframe

Testez la même période avec différents intervalles :
- 15m : Scalping rapide
- 30m : Court terme
- 1h : Moyen terme
- 4h : Swing trading

Comparez les métriques et choisissez le meilleur compromis rendement/risque.

---

## 🔧 Optimisation de la stratégie

### Paramètres à tester

1. **Intervalle de temps**
   - Plus court (5m, 15m) = Plus de trades, plus de faux signaux
   - Plus long (4h, 1d) = Moins de trades, signaux plus fiables

2. **Risque par trade**
   - 0.5% = Très conservateur
   - 1% = Équilibré (recommandé)
   - 2-3% = Agressif

3. **Position maximale**
   - Limite les pertes sur un seul trade
   - Recommandé : 10% du capital

### Méthode d'optimisation

1. **Test de base** : Paramètres par défaut sur 30 jours
2. **Variation d'un paramètre** : Changez uniquement l'intervalle
3. **Comparaison** : Notez les résultats
4. **Itération** : Testez d'autres valeurs
5. **Validation** : Test sur une période différente

**⚠️ Attention à l'overfitting !**
Ne sur-optimisez pas sur une seule période. Testez toujours sur plusieurs périodes différentes.

---

## ❓ FAQ

### Le backtest est-il précis ?

**Avantages :**
- ✅ Utilise de vraies données de Binance
- ✅ Simule exactement la stratégie du bot réel
- ✅ Inclut les pivots, breakouts, cooldowns

**Limitations :**
- ❌ N'inclut pas les frais de trading (ajouter ~0.1% par trade)
- ❌ N'inclut pas le slippage (différence entre prix attendu et réel)
- ❌ Assume l'exécution instantanée (peut différer en production)
- ❌ Pas de simulation du spread bid/ask

**Conclusion :** Les résultats sont une bonne approximation, mais attendez-vous à **5-10% de différence** en production.

### Combien de jours tester ?

**Recommandations :**
- **Minimum** : 14 jours (2 semaines)
- **Idéal** : 30-60 jours (1-2 mois)
- **Validation** : 90+ jours (3 mois)

**Considérations :**
- Courte période (< 14j) : Peut être chance/malchance
- Longue période (> 90j) : Marché peut avoir changé
- **Mieux** : Plusieurs périodes de 30j en différentes conditions de marché

### Que faire si les résultats sont mauvais ?

1. **Vérifiez le contexte de marché**
   - Marché range vs tendance
   - La stratégie 3 Swings fonctionne mieux en tendance

2. **Testez d'autres intervalles**
   - Certains timeframes fonctionnent mieux selon les actifs

3. **Ajustez le risque**
   - Peut-être trop agressif ou trop conservateur

4. **Changez d'actif**
   - Certaines paires sont plus adaptées (volatilité, volume)

5. **Acceptez les limites**
   - Aucune stratégie ne gagne 100% du temps
   - Un win rate de 50-60% est déjà excellent

### Puis-je faire du backtesting sur d'autres paires ?

**Oui !** Testez n'importe quelle paire USDT de Binance :
- BTCUSDT, ETHUSDT (recommandé pour débuter)
- BNBUSDT, SOLUSDT, ADAUSDT
- Paires de petite cap (plus volatiles, plus risquées)

**Astuce :** Les grandes caps (BTC, ETH) ont généralement de meilleurs résultats car :
- Plus de volume (meilleure exécution)
- Moins de manipulation
- Pivots plus clairs

---

## 📚 Ressources supplémentaires

### Documentation

- **ARCHITECTURE.md** : Architecture technique du système
- **README.md** : Guide de démarrage rapide
- **bot_core.py** : Code source de la stratégie 3 Swings

### Support

Si vous rencontrez des problèmes :
1. Vérifiez que toutes les dépendances sont installées
2. Vérifiez vos clés API Binance
3. Consultez les logs d'erreur dans le terminal
4. Testez d'abord avec le Testnet

---

## ⚡ Conseils Pro

1. **Commencez petit** : Testez d'abord sur 7 jours avec le Testnet
2. **Documentez vos tests** : Notez les paramètres et résultats
3. **Testez différentes périodes** : Bull market, bear market, range
4. **Comparez avec Buy & Hold** : Votre stratégie doit battre l'achat simple
5. **Ne sur-optimisez pas** : Des résultats trop parfaits sont suspects
6. **Validez en paper trading** : Avant le réel, testez en dry_run live
7. **Gérez vos attentes** : Visez 5-15% par mois, pas 100%

---

## 🎓 Conclusion

Le backtesting est un outil puissant mais n'est pas une garantie de succès futur. Utilisez-le pour :
- ✅ Comprendre comment fonctionne la stratégie
- ✅ Identifier les conditions de marché favorables
- ✅ Optimiser les paramètres
- ✅ Valider avant de risquer du capital réel

**Les performances passées ne préjugent pas des résultats futurs.**

Bonne chance avec votre trading ! 🚀
