# sqlite storage helpers
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = "mbot.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS trades(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  price REAL NOT NULL,
  notional REAL NOT NULL,
  pnl REAL,
  extra TEXT
);
CREATE TABLE IF NOT EXISTS positions(
  symbol TEXT PRIMARY KEY,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  entry_price REAL NOT NULL,
  updated_ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS logs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  symbol TEXT,
  level TEXT NOT NULL,
  message TEXT NOT NULL
);
"""

def get_conn():
  return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
  con = get_conn()
  try:
    cur = con.cursor()
    for stmt in SCHEMA.strip().split(";"):
      s = stmt.strip()
      if s:
        cur.execute(s)
    con.commit()
  finally:
    con.close()

def log(symbol: Optional[str], level: str, message: str):
  con = get_conn()
  try:
    cur = con.cursor()
    cur.execute("INSERT INTO logs(ts, symbol, level, message) VALUES (?,?,?,?)",
                (datetime.utcnow().isoformat(), symbol, level, message))
    con.commit()
  finally:
    con.close()

def upsert_position(symbol: str, side: str, qty: float, entry_price: float):
  con = get_conn()
  try:
    cur = con.cursor()
    cur.execute("""INSERT INTO positions(symbol, side, qty, entry_price, updated_ts)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(symbol) DO UPDATE SET
                   side=excluded.side, qty=excluded.qty, entry_price=excluded.entry_price, updated_ts=excluded.updated_ts
                """, (symbol, side, qty, entry_price, datetime.utcnow().isoformat()))
    con.commit()
  finally:
    con.close()

def clear_position(symbol: str):
  con = get_conn()
  try:
    cur = con.cursor()
    cur.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
    con.commit()
  finally:
    con.close()

def insert_trade(symbol: str, side: str, qty: float, price: float, pnl: float=None, extra: str=""):
  con = get_conn()
  try:
    cur = con.cursor()
    cur.execute("""INSERT INTO trades(ts, symbol, side, qty, price, notional, pnl, extra)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (datetime.utcnow().isoformat(), symbol, side, qty, price, qty*price, pnl, extra))
    con.commit()
  finally:
    con.close()

def fetch_trades(symbol: Optional[str]=None) -> List[Dict[str, Any]]:
  con = get_conn()
  con.row_factory = sqlite3.Row
  try:
    cur = con.cursor()
    if symbol:
      cur.execute("SELECT * FROM trades WHERE symbol=? ORDER BY id DESC", (symbol,))
    else:
      cur.execute("SELECT * FROM trades ORDER BY id DESC")
    rows = cur.fetchall()
    return [dict(r) for r in rows]
  finally:
    con.close()

def fetch_positions() -> List[Dict[str, Any]]:
  con = get_conn()
  con.row_factory = sqlite3.Row
  try:
    cur = con.cursor()
    cur.execute("SELECT * FROM positions ORDER BY symbol")
    rows = cur.fetchall()
    return [dict(r) for r in rows]
  finally:
    con.close()

def fetch_logs(symbol: Optional[str]=None, limit: int=200) -> List[Dict[str, Any]]:
  con = get_conn()
  con.row_factory = sqlite3.Row
  try:
    cur = con.cursor()
    if symbol:
      cur.execute("SELECT * FROM logs WHERE symbol=? ORDER BY id DESC LIMIT ?", (symbol, limit))
    else:
      cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]
  finally:
    con.close()
