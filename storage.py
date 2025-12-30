"""
Module de gestion de la base de données SQLite pour le dashboard multi-bots.
Stocke les trades, positions et logs de tous les bots.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = Path(__file__).parent / "bot_data.db"


def init_db():
    """Initialise la base de données avec les tables nécessaires."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table des trades
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            quote_qty REAL NOT NULL,
            pnl REAL,
            ts TEXT NOT NULL,
            order_id TEXT,
            entry_price REAL,
            notes TEXT
        )
    """)

    # Table des positions actuelles
    c.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            entry_price REAL NOT NULL,
            current_price REAL,
            pnl_unrealized REAL,
            last_update TEXT NOT NULL
        )
    """)

    # Table des logs
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            ts TEXT NOT NULL
        )
    """)

    # Table des bots en cours d'exécution
    c.execute("""
        CREATE TABLE IF NOT EXISTS running_bots (
            symbol TEXT PRIMARY KEY,
            interval TEXT NOT NULL,
            risk_pct REAL NOT NULL,
            max_pos REAL NOT NULL,
            testnet INTEGER NOT NULL,
            dry_run INTEGER NOT NULL,
            api_key TEXT NOT NULL,
            api_secret TEXT NOT NULL,
            started_at TEXT NOT NULL,
            last_heartbeat TEXT
        )
    """)

    conn.commit()
    conn.close()


def insert_trade(symbol: str, side: str, qty: float, price: float,
                 quote_qty: float, pnl: Optional[float] = None,
                 order_id: Optional[str] = None, entry_price: Optional[float] = None,
                 notes: Optional[str] = None):
    """Enregistre un trade dans la base de données."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    ts = datetime.now().isoformat()

    c.execute("""
        INSERT INTO trades (symbol, side, qty, price, quote_qty, pnl, ts, order_id, entry_price, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, side, qty, price, quote_qty, pnl, ts, order_id, entry_price, notes))

    conn.commit()
    conn.close()


def update_position(symbol: str, side: str, qty: float, entry_price: float,
                   current_price: Optional[float] = None, pnl_unrealized: Optional[float] = None):
    """Met à jour la position actuelle pour un symbole."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    ts = datetime.now().isoformat()

    c.execute("""
        INSERT OR REPLACE INTO positions
        (symbol, side, qty, entry_price, current_price, pnl_unrealized, last_update)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (symbol, side, qty, entry_price, current_price, pnl_unrealized, ts))

    conn.commit()
    conn.close()


def clear_position(symbol: str):
    """Supprime la position pour un symbole (quand on est FLAT)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))

    conn.commit()
    conn.close()


def insert_log(symbol: Optional[str], level: str, message: str):
    """Enregistre un log dans la base de données."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    ts = datetime.now().isoformat()

    c.execute("""
        INSERT INTO logs (symbol, level, message, ts)
        VALUES (?, ?, ?, ?)
    """, (symbol, level, message, ts))

    conn.commit()
    conn.close()


def fetch_trades(symbol: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """Récupère les trades depuis la base de données."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if symbol:
        c.execute("""
            SELECT * FROM trades
            WHERE symbol = ?
            ORDER BY ts DESC
            LIMIT ?
        """, (symbol, limit))
    else:
        c.execute("""
            SELECT * FROM trades
            ORDER BY ts DESC
            LIMIT ?
        """, (limit,))

    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def fetch_positions() -> List[Dict]:
    """Récupère toutes les positions actuelles."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM positions ORDER BY symbol")

    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def fetch_logs(symbol: Optional[str] = None, limit: int = 200) -> List[Dict]:
    """Récupère les logs depuis la base de données."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if symbol:
        c.execute("""
            SELECT * FROM logs
            WHERE symbol = ? OR symbol IS NULL
            ORDER BY ts DESC
            LIMIT ?
        """, (symbol, limit))
    else:
        c.execute("""
            SELECT * FROM logs
            ORDER BY ts DESC
            LIMIT ?
        """, (limit,))

    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def save_running_bot(symbol: str, interval: str, risk_pct: float, max_pos: float,
                     testnet: bool, dry_run: bool, api_key: str, api_secret: str):
    """Enregistre un bot en cours d'exécution dans la base de données."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    ts = datetime.now().isoformat()

    c.execute("""
        INSERT OR REPLACE INTO running_bots
        (symbol, interval, risk_pct, max_pos, testnet, dry_run, api_key, api_secret, started_at, last_heartbeat)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (symbol, interval, risk_pct, max_pos, int(testnet), int(dry_run), api_key, api_secret, ts, ts))

    conn.commit()
    conn.close()


def update_bot_heartbeat(symbol: str):
    """Met à jour le heartbeat d'un bot en cours d'exécution."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    ts = datetime.now().isoformat()

    c.execute("""
        UPDATE running_bots
        SET last_heartbeat = ?
        WHERE symbol = ?
    """, (ts, symbol))

    conn.commit()
    conn.close()


def remove_running_bot(symbol: str):
    """Supprime un bot de la liste des bots en cours d'exécution."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DELETE FROM running_bots WHERE symbol = ?", (symbol,))

    conn.commit()
    conn.close()


def fetch_running_bots() -> List[Dict]:
    """Récupère tous les bots censés être en cours d'exécution."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM running_bots ORDER BY symbol")

    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows]
