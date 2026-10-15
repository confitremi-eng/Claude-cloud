import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Candidate signal families. Each returns a list of (i, dir, stop_price) — stop is the natural invalidation level."""
import numpy as np
import pandas as pd
from bt import ema, atr, signals as v3_signals, TICK


def fam_reversal(df, N=20, **kw):
    return [(i, d, sw - d * TICK) for i, d, sw, j in v3_signals(df, N=N, **kw)]


def fam_pullback(df, N=8, trend=None, ema_on=True, E=8):
    """v3 trigger on a shallow N-bar pullback, only in the trend direction."""
    out = []
    for i, d, sw, j in v3_signals(df, N=N, E=E, ema_on=ema_on):
        if trend is None or trend[i] == d:
            out.append((i, d, sw - d * TICK))
    return out


def fam_breakout(df, N=20, trend=None, stopN=10):
    """Close crosses above the prior N-bar high (below the N-bar low); stop = stopN-bar low/high."""
    h, l, c = df.high.values, df.low.values, df.close.values
    hh = pd.Series(h).rolling(N).max().shift().values; ll = pd.Series(l).rolling(N).min().shift().values
    sl = pd.Series(l).rolling(stopN).min().values; sh = pd.Series(h).rolling(stopN).max().values
    out = []
    for i in range(N + 1, len(c)):
        if c[i] > hh[i] and c[i - 1] <= hh[i - 1] and (trend is None or trend[i] == 1):
            out.append((i, 1, sl[i] - TICK))
        if c[i] < ll[i] and c[i - 1] >= ll[i - 1] and (trend is None or trend[i] == -1):
            out.append((i, -1, sh[i] + TICK))
    return out


def fam_ema_pullback(df, fast=20, trend=None, look=5):
    """In trend: price touched EMA(fast) within `look` bars, then closes beyond the prior bar's high/low and EMA."""
    h, l, c = df.high.values, df.low.values, df.close.values
    e = ema(c, fast)
    touchL = pd.Series(l <= e).rolling(look).max().values.astype(bool)
    touchH = pd.Series(h >= e).rolling(look).max().values.astype(bool)
    lowL = pd.Series(l).rolling(look).min().values; highH = pd.Series(h).rolling(look).max().values
    out = []
    armB = armS = True
    for i in range(look + 1, len(c)):
        if trend is not None and trend[i] == 1 and touchL[i] and c[i] > h[i - 1] and c[i] > e[i] and c[i - 1] <= h[i - 2]:
            out.append((i, 1, lowL[i] - TICK))
        if trend is not None and trend[i] == -1 and touchH[i] and c[i] < l[i - 1] and c[i] < e[i] and c[i - 1] >= l[i - 2]:
            out.append((i, -1, highH[i] + TICK))
    return out


def trade(df, sigs, exit='R', R=1.5, k=3.0, horizon=120, cost=1.0, warm=30, min_risk=None, opp=None):
    """Simulate independent trades. exit: 'R' fixed target, 'chand' ATR chandelier trail, 'opp' opposite signal."""
    h, l, c = df.high.values, df.low.values, df.close.values
    a = atr(h, l, c)
    n = len(df); blk = df.block.values; bib = df.bar_in_block.values
    blk_end = pd.Series(np.arange(n)).groupby(blk).transform('max').values
    opp_at = {}
    if opp is not None:
        for i, d, s in opp: opp_at.setdefault(i, set()).add(d)
    rows = []
    for i, d, stop in sigs:
        if bib[i] < warm: continue
        entry = c[i]; risk = (entry - stop) * d
        if min_risk is not None and risk < min_risk * a[i]:
            stop = entry - d * min_risk * a[i]; risk = min_risk * a[i]
        if risk <= 0: continue
        end = min(blk_end[i], i + horizon); out = None; peak = entry
        tgt = entry + d * R * risk
        for t in range(i + 1, end + 1):
            if (l[t] <= stop) if d == 1 else (h[t] >= stop):
                out = (stop - entry) * d; break
            if exit == 'R' and ((h[t] >= tgt) if d == 1 else (l[t] <= tgt)):
                out = R * risk; break
            if exit == 'opp' and -d in opp_at.get(t, ()):
                out = (c[t] - entry) * d; break
            if exit == 'chand':
                peak = max(peak, h[t]) if d == 1 else min(peak, l[t])
                trail = peak - d * k * a[t]
                stop = max(stop, trail) if d == 1 else min(stop, trail)
        if out is None: out = (c[end] - entry) * d
        rows.append((i, d, (out - cost) / risk, out - cost, df.datetime.iloc[i]))
    return pd.DataFrame(rows, columns=['i', 'dir', 'R', 'pts', 'time'])


def stats(t):
    if len(t) < 5: return dict(n=len(t))
    w = t.R[t.R > 0].sum(); L = -t.R[t.R < 0].sum()
    return dict(n=len(t), win=round(100 * (t.R > 0).mean(), 1), expR=round(t.R.mean(), 3),
                pf=round(w / L, 2) if L else np.inf, pts=round(t.pts.mean(), 2))
