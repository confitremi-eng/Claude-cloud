import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Trend contexts (no look-ahead): each returns +1 up / -1 down / 0 flat per bar."""
import numpy as np
import pandas as pd
from bt import ema, rma


def ema_slope(df, n=100, lb=10):
    e = ema(df.close.values, n)
    s = np.sign(e - np.r_[np.full(lb, np.nan), e[:-lb]])
    return np.nan_to_num(s)


def px_vs_ema(df, n=200):
    e = ema(df.close.values, n)
    return np.sign(df.close.values - e)


def ema_cross(df, fast=50, slow=200):
    return np.sign(ema(df.close.values, fast) - ema(df.close.values, slow))


def htf_ema(df, tf_minutes=15, n=20):
    """Higher-timeframe EMA slope, using only completed HTF bars."""
    d = df.set_index('datetime')
    htf = d.close.resample(f'{tf_minutes}min').last().dropna()
    e = pd.Series(ema(htf.values, n), index=htf.index)
    slope = np.sign(e.diff())
    # an HTF bar labelled t (left edge) completes at t + tf; usable from then on
    slope.index = slope.index + pd.Timedelta(minutes=tf_minutes)
    m = slope.reindex(d.index, method='ffill')
    return np.nan_to_num(m.values)


def consensus(df, factor=7):
    """The indicator's 10-vote consensus (MACD x2, RSI, Stoch x2, DMI, ADX, Momentum, CCI, EMA20)."""
    h, l, c = df.high.values, df.low.values, df.close.values
    fast, slow = ema(c, 12), ema(c, 26)
    macd = fast - slow; sig = ema(macd, 9); hist = macd - sig
    d = np.diff(c, prepend=c[0]); up = rma(np.maximum(d, 0), 14); dn = rma(np.maximum(-d, 0), 14)
    rsi = 100 - 100 / (1 + up / np.where(dn == 0, np.nan, dn)); rsi = np.nan_to_num(rsi, nan=50)
    ll = pd.Series(l).rolling(14).min().values; hh = pd.Series(h).rolling(14).max().values
    k = pd.Series(100 * (c - ll) / np.where(hh - ll == 0, np.nan, hh - ll)).rolling(3).mean().values
    dd = pd.Series(k).rolling(3).mean().values
    uph = np.diff(h, prepend=h[0]); dnl = -np.diff(l, prepend=l[0])
    pdm = np.where((uph > dnl) & (uph > 0), uph, 0.0); mdm = np.where((dnl > uph) & (dnl > 0), dnl, 0.0)
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc))); trr = rma(tr, 14)
    pdi = 100 * rma(pdm, 14) / trr; mdi = 100 * rma(mdm, 14) / trr
    dx = 100 * np.abs(pdi - mdi) / np.where(pdi + mdi == 0, 1, pdi + mdi); adx = rma(dx, 14)
    adxup = adx > np.r_[adx[0], adx[:-1]]
    mom = c - np.r_[np.full(10, np.nan), c[:-10]]
    tp = (h + l + c) / 3; ma = pd.Series(tp).rolling(20).mean().values
    md = pd.Series(tp).rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True).values
    cci = (tp - ma) / (0.015 * np.where(md == 0, np.nan, md))
    e20 = ema(c, 20)
    v = lambda bull, bear: np.where(bull, 1, np.where(bear, -1, 0))
    votes = [v(macd > sig, macd < sig), v(hist > np.r_[hist[0], hist[:-1]], hist < np.r_[hist[0], hist[:-1]]),
             v(rsi > 50, rsi < 50), v(k > dd, k < dd), v(k > 50, k < 50), v(pdi > mdi, pdi < mdi),
             v(adxup & (pdi > mdi), adxup & (pdi < mdi)), v(mom > 0, mom < 0), v(cci > 0, cci < 0), v(c > e20, c < e20)]
    V = np.vstack(votes)
    bull = (V > 0).sum(0); bear = (V < 0).sum(0)
    return np.where((bull >= factor) & (bull > bear), 1, np.where((bear >= factor) & (bear > bull), -1, 0))
