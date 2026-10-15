import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Backtest helpers for the BO Signals rule family (NQ 1-minute sample, resampled)."""
import numpy as np
import pandas as pd

import os
DATA = os.environ.get('NQ_DATA', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'NQ_1m.csv'))
TICK = 0.25


def load(tf=1):
    df = pd.read_csv(DATA, parse_dates=['datetime']).set_index('datetime').sort_index()
    if tf == 1:
        df = df.reset_index()
        gap = df.datetime.diff() > pd.Timedelta(minutes=1)
        df['block'] = gap.cumsum()
        df['bar_in_block'] = df.groupby('block').cumcount()
        return df
    if tf > 1:
        # resample inside each contiguous block so bars never span a session gap
        block = (df.index.to_series().diff() != pd.Timedelta('1min')).cumsum()
        parts = []
        for _, g in df.groupby(block):
            r = g.resample(f'{tf}min', origin=g.index[0]).agg(
                {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
            parts.append(r)
        df = pd.concat(parts)
    df = df.reset_index()
    gap = df.datetime.diff() > pd.Timedelta(minutes=tf)
    df['block'] = gap.cumsum()
    df['bar_in_block'] = df.groupby('block').cumcount()
    return df


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def rma(x, n):
    return pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().values


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return rma(tr, n)


def signals(df, N=20, E=8, src='hl2', ema_on=True, consume=True, max_wait=None, trigger='swingbar'):
    """v3 rule. Returns list of (i, dir, swing_extreme, swing_index).
    trigger='swingbar': first close beyond the swing bar's high/low.
    trigger='prevbar' : first close beyond the previous bar's high/low (after the swing)."""
    h, l, c = df.high.values, df.low.values, df.close.values
    s = (h + l) / 2 if src == 'hl2' else c
    e = ema(s, E)
    n = len(df)
    lowest_prev = pd.Series(l).rolling(N).min().shift().values
    highest_prev = pd.Series(h).rolling(N).max().shift().values
    out = []
    armB = armS = False
    refB = refS = np.nan
    swB = swS = np.nan
    tB = tS = -1
    for i in range(n):
        newLow = l[i] < lowest_prev[i] if not np.isnan(lowest_prev[i]) else False
        newHigh = h[i] > highest_prev[i] if not np.isnan(highest_prev[i]) else False
        levB = refB if trigger == 'swingbar' else (h[i - 1] if i > 0 else np.nan)
        levS = refS if trigger == 'swingbar' else (l[i - 1] if i > 0 else np.nan)
        trigB = (not newLow) and armB and c[i] > levB and (max_wait is None or i - tB <= max_wait)
        trigS = (not newHigh) and armS and c[i] < levS and (max_wait is None or i - tS <= max_wait)
        if armB and max_wait is not None and i - tB > max_wait:
            armB = False
        if armS and max_wait is not None and i - tS > max_wait:
            armS = False
        okB = (not ema_on) or c[i] > e[i]
        okS = (not ema_on) or c[i] < e[i]
        if trigB and okB:
            out.append((i, 1, swB, tB))
        if trigS and okS:
            out.append((i, -1, swS, tS))
        if newLow:
            armB, refB, swB, tB = True, h[i], l[i], i
        elif trigB and (consume or okB):
            armB = False
        if newHigh:
            armS, refS, swS, tS = True, l[i], h[i], i
        elif trigS and (consume or okS):
            armS = False
    return out


def simulate(df, sigs, targets=(1.0, 1.5, 2.0, 3.0), horizon=60, cost=1.0, stop_buf=TICK,
             min_risk_atr=0.0, a=None, warm=30):
    """Each signal is an independent trade: entry = signal close, stop = swing extreme -/+ buffer.
    Returns DataFrame with R results per target (net of round-trip cost in points)."""
    h, l, c = df.high.values, df.low.values, df.close.values
    if a is None:
        a = atr(h, l, c)
    rows = []
    n = len(df)
    blk = df.block.values; bib = df.bar_in_block.values
    blk_end = pd.Series(np.arange(n)).groupby(blk).transform('max').values
    for i, d, sw, j in sigs:
        if bib[i] < warm or blk[j] != blk[i]:
            continue
        entry = c[i]
        stop = sw - stop_buf if d == 1 else sw + stop_buf
        risk = (entry - stop) * d
        if min_risk_atr > 0 and risk < min_risk_atr * a[i]:
            stop = entry - d * min_risk_atr * a[i]
            risk = min_risk_atr * a[i]
        if risk <= 0:
            continue
        res = {}
        end = min(blk_end[i], i + horizon)
        if end <= i:
            continue
        mfe = mae = 0.0
        for t in targets:
            tgt = entry + d * t * risk
            out = None
            for k in range(i + 1, end + 1):
                hit_stop = (l[k] <= stop) if d == 1 else (h[k] >= stop)
                hit_tgt = (h[k] >= tgt) if d == 1 else (l[k] <= tgt)
                if hit_stop:                      # stop first when both happen in one bar
                    out = -1.0
                    break
                if hit_tgt:
                    out = t
                    break
            if out is None:                       # time exit
                out = (c[end] - entry) * d / risk
            res[f'R{t}'] = out - cost / risk
        for k in range(i + 1, end + 1):
            mfe = max(mfe, ((h[k] - entry) if d == 1 else (entry - l[k])) / risk)
            mae = max(mae, ((entry - l[k]) if d == 1 else (h[k] - entry)) / risk)
        rows.append(dict(i=i, dir=d, entry=entry, risk=risk, risk_atr=risk / a[i], mfe=mfe, mae=mae,
                         fwd10=(c[min(blk_end[i], i + 10)] - entry) * d / a[i],
                         fwd30=(c[min(blk_end[i], i + 30)] - entry) * d / a[i], **res))
    return pd.DataFrame(rows)


def summarize(t, col='R1.5'):
    if len(t) == 0:
        return dict(n=0)
    r = t[col]
    wins = r[r > 0].sum(); losses = -r[r < 0].sum()
    return dict(n=len(t), win=round((r > 0).mean() * 100, 1), expR=round(r.mean(), 3),
                pf=round(wins / losses, 2) if losses > 0 else np.inf, totR=round(r.sum(), 1),
                risk_pts=round(t.risk.median(), 1))
