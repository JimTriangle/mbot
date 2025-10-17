# core multi-bot engine
import os, time, math, json, threading
from typing import Dict, Any, Tuple
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from storage import init_db, log as dblog, insert_trade, upsert_position, clear_position

# ===== Indicators (Pine-equivalent) =====
def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def rsi(series: pd.Series, length: int=14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=length).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=length).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    return rsi_val.fillna(50)

def dmi_adx(high: pd.Series, low: pd.Series, close: pd.Series, length: int=14, smoothing: int=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr = tr.rolling(window=length).mean()
    plus_di = 100 * (plus_dm.rolling(window=length).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(window=length).mean() / atr.replace(0, np.nan))
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.rolling(window=smoothing).mean()
    return plus_di.fillna(0), minus_di.fillna(0), adx.fillna(0)

def symbol_filters(client: Client, symbol: str):
    info = client.get_symbol_info(symbol)
    if not info: raise RuntimeError(f"Symbole introuvable: {symbol}")
    return {f['filterType']: f for f in info['filters']}

def round_step_size(quantity: float, step_size: float) -> float:
    if step_size <= 0: return quantity
    return math.floor(quantity / step_size) * step_size

def conform_qty_and_notional(qty: float, price: float, filters: Dict[str, Any]) -> float:
    lot = filters.get("LOT_SIZE", {})
    min_qty = float(lot.get("minQty", 0))
    max_qty = float(lot.get("maxQty", 1e12))
    step = float(lot.get("stepSize", 0.00000001))

    mnot = filters.get("MIN_NOTIONAL", {})
    min_notional = float(mnot.get("minNotional", 0))

    qty = max(min_qty, min(qty, max_qty))
    qty = round_step_size(qty, step)

    if qty * price < min_notional:
        qty = round_step_size((min_notional / price) * 1.01, step)

    return qty

def fetch_klines_df(client: Client, symbol: str, interval: str, limit: int=500) -> pd.DataFrame:
    kl = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    cols = ["open_time","open","high","low","close","volume","close_time","qav","num_trades","tbbav","tbqav","ignore"]
    df = pd.DataFrame(kl, columns=cols)
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    return df

class TrendPhases:
    def __init__(self, ema_short=20, ema_long=50, rsi_len=14, adx_len=14, adx_smooth=14,
                 adx_thr=25, rsi_up=55.0, rsi_down=35.0):
        self.ema_short=ema_short; self.ema_long=ema_long
        self.rsi_len=rsi_len; self.adx_len=adx_len; self.adx_smooth=adx_smooth
        self.adx_thr=adx_thr; self.rsi_up=rsi_up; self.rsi_down=rsi_down

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["emaShort"] = ema(out["close"], self.ema_short)
        out["emaLong"]  = ema(out["close"], self.ema_long)
        out["rsi"]      = rsi(out["close"], self.rsi_len)
        plusDI, minusDI, adxVal = dmi_adx(out["high"], out["low"], out["close"], self.adx_len, self.adx_smooth)
        out["plusDI"], out["minusDI"], out["adxVal"] = plusDI, minusDI, adxVal

        out["strongUpTrend"] = (
            (out["emaShort"] > out["emaLong"]) &
            (out["plusDI"] > out["minusDI"]) &
            (out["rsi"] > self.rsi_up) &
            (out["adxVal"] > self.adx_thr) &
            (out["emaShort"] > out["emaShort"].shift(1))
        )
        out["strongDownTrend"] = (
            (out["emaShort"] < out["emaLong"]) &
            (out["minusDI"] > out["plusDI"]) &
            (out["rsi"] < self.rsi_down) &
            (out["adxVal"] > self.adx_thr) &
            (out["emaShort"] < out["emaShort"].shift(1))
        )
        out["debutHausse"] = out["strongUpTrend"] & (~out["strongUpTrend"].shift(1).fillna(False))
        out["debutBaisse"] = out["strongDownTrend"] & (~out["strongDownTrend"].shift(1).fillna(False))
        out["finHausse"] = out["strongUpTrend"].shift(1).fillna(False) & (~out["strongUpTrend"])
        out["finBaisse"] = out["strongDownTrend"].shift(1).fillna(False) & (~out["strongDownTrend"])
        return out

class Bot(threading.Thread):
    def __init__(self, symbol: str, interval: str, risk_pct: float, max_pos: float,
                 testnet: bool, dry_run: bool, api_key: str, api_secret: str,
                 lookback: int=500, sleep_s: int=2):
        super().__init__(daemon=True)
        self.symbol=symbol; self.interval=interval
        self.risk_pct=risk_pct; self.max_pos=max_pos
        self.testnet=testnet; self.dry_run=dry_run
        self.api_key=api_key; self.api_secret=api_secret
        self.lookback=lookback; self.sleep_s=sleep_s
        self._stop = threading.Event()
        self.client = Client(api_key, api_secret, testnet=testnet)
        self.strat = TrendPhases()
        self.pos_side="FLAT"; self.pos_qty=0.0; self.entry_price=0.0
        self.last_close_time=None

    def run(self):
        dblog(self.symbol, "INFO", f"Bot start testnet={self.testnet} dry_run={self.dry_run}")
        try:
            df = fetch_klines_df(self.client, self.symbol, self.interval, self.lookback)
            self.last_close_time = df["close_time"].iloc[-1]
        except Exception as e:
            dblog(self.symbol, "ERROR", f"Init klines failed: {e}")
            return

        while not self._stop.is_set():
            try:
                time.sleep(self.sleep_s)
                new_df = fetch_klines_df(self.client, self.symbol, self.interval, self.lookback)
                nct = new_df["close_time"].iloc[-1]
                if self.last_close_time and nct <= self.last_close_time:
                    continue
                self.last_close_time = nct

                calc = self.strat.compute(new_df)
                row = calc.iloc[-1]
                price = float(row["close"])

                debutHausse = bool(row["debutHausse"])
                debutBaisse = bool(row["debutBaisse"])
                finHausse   = bool(row["finHausse"])
                finBaisse   = bool(row["finBaisse"])

                dblog(self.symbol, "DEBUG", json.dumps({
                    "close_time": str(nct), "price": price,
                    "signals": {"debutHausse": debutHausse, "debutBaisse": debutBaisse,
                                "finHausse": finHausse, "finBaisse": finBaisse},
                    "pos": {"side": self.pos_side, "qty": self.pos_qty, "entry": self.entry_price}
                }))

                if self.pos_side == "LONG":
                    if debutBaisse or finHausse:
                        qty = self.pos_qty
                        if qty > 0:
                            self._sell_market(qty)
                            pnl = (price - self.entry_price) * qty
                            insert_trade(self.symbol, "SELL", qty, price, pnl=pnl, extra="exit")
                        self._set_flat()
                else:
                    if debutHausse:
                        price_now = float(self.client.get_symbol_ticker(symbol=self.symbol)["price"])
                        qty = self._compute_qty(price_now)
                        if qty > 0:
                            self._buy_market(qty)
                            insert_trade(self.symbol, "BUY", qty, price_now, pnl=None, extra="entry")
                            self._set_long(qty, price_now)

            except (BinanceAPIException, BinanceRequestException) as e:
                dblog(self.symbol, "ERROR", f"Binance: {e}")
            except Exception as e:
                dblog(self.symbol, "ERROR", f"Loop: {e}")

        dblog(self.symbol, "INFO", "Bot stopped.")

    def stop(self):
        self._stop.set()

    def _compute_qty(self, price: float) -> float:
        # Quote asset inference for common suffixes
        quote = "USDT" if self.symbol.endswith("USDT") else self.symbol[-3:]
        bal = 0.0
        try:
            acc = self.client.get_account()
            for b in acc["balances"]:
                if b["asset"] == quote:
                    bal = float(b["free"])
                    break
        except Exception as e:
            dblog(self.symbol, "ERROR", f"get_account failed: {e}")

        amount = bal * self.risk_pct
        if self.max_pos > 0:
            amount = min(amount, self.max_pos)
        raw_qty = amount / price if price>0 else 0.0

        filt = symbol_filters(self.client, self.symbol)
        qty = conform_qty_and_notional(raw_qty, price, filt)
        return qty

    def _buy_market(self, qty: float):
        if self.dry_run:
            dblog(self.symbol, "INFO", f"DRY_RUN BUY {qty}")
            return
        resp = self.client.create_order(symbol=self.symbol, side="BUY", type="MARKET", quantity=qty)
        dblog(self.symbol, "INFO", f"BUY -> {resp}")

    def _sell_market(self, qty: float):
        if self.dry_run:
            dblog(self.symbol, "INFO", f"DRY_RUN SELL {qty}")
            return
        resp = self.client.create_order(symbol=self.symbol, side="SELL", type="MARKET", quantity=qty)
        dblog(self.symbol, "INFO", f"SELL -> {resp}")

    def _set_long(self, qty: float, price: float):
        self.pos_side="LONG"; self.pos_qty=qty; self.entry_price=price
        upsert_position(self.symbol, "LONG", qty, price)

    def _set_flat(self):
        self.pos_side="FLAT"; self.pos_qty=0.0; self.entry_price=0.0
        clear_position(self.symbol)
