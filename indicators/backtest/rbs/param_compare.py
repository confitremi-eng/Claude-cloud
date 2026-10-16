"""Remi's Buy/Sell parameters on NQ 1m and 2m (Databento year): (20,0,8,1), (20,0,8,0) EMA off, (30,0,13,1).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/param_compare.py

Same exits as setup_study.py (stop at the extreme of the signal bar and the one before, fixed R target,
60-bar time exit, 1 point cost) and the same trend levels, from all signals to the recommended rule.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import warnings; warnings.simplefilter('ignore', FutureWarning)
import numpy as np
import pandas as pd
from rbs import prepared
from remi_export import signals
from setup_study import bar_context, outcome, hourly, add_context, seq, stats, fmt, HORIZON, COST, SPLIT, TARGETS

SETS = {'(20,0,8,1)': (20, 8, True), '(20,0,8,0)': (20, 8, False), '(30,0,13,1)': (30, 13, True)}
EVT = lambda x: x.ev_data | x.ev_open | x.ev_close | x.ev_globex
GROUPS = [('全部訊號', lambda x: x.side != 0),
          ('TJ 順勢（一般 + 強）', lambda x: x.side * x.dir >= 1),
          ('  UP + Buy', lambda x: (x.side == 1) & (x.dir == 1)),
          ('  強UP + Buy', lambda x: (x.side == 1) & (x.dir == 2)),
          ('  DOWN + Sell', lambda x: (x.side == -1) & (x.dir == -1)),
          ('  強Down + Sell', lambda x: (x.side == -1) & (x.dir == -2)),
          ('TJ 順勢 + 1h 同向', lambda x: (x.side * x.dir >= 1) & (x.side == x.h1)),
          ('  同上，只看現金盤', lambda x: (x.side * x.dir >= 1) & (x.side == x.h1) & x.rth),
          ('推薦規則全套', lambda x: (x.side * x.dir >= 1) & (x.side == x.h1) & ~EVT(x) & ~x.asia & (x.risk_atr >= 1))]
QUADRANT = lambda name: name.startswith(('  U', '  強', '  D'))


def sigs(df, stage, ema_len, ema_on):
    """remi_export.signals with the stage, EMA length and Ema enable as parameters."""
    h, l, c = df.high.values, df.low.values, df.close.values
    ema = pd.Series(c).ewm(span=ema_len, adjust=False).mean().values
    lo = pd.Series(l).rolling(stage).min().shift().values
    hi = pd.Series(h).rolling(stage).max().shift().values
    n = len(c); B = np.zeros(n, int); S = np.zeros(n, int)
    armB = armS = False; refH = refL = np.nan
    for i in range(stage, n):
        newLow, newHigh = l[i] < lo[i], h[i] > hi[i]
        trigB = armB and c[i] > refH; trigS = armS and c[i] < refL
        B[i] = trigB and (not ema_on or c[i] > ema[i]); S[i] = trigS and (not ema_on or c[i] < ema[i])
        if trigB: armB = False
        elif newLow: armB, refH = True, h[i]
        if trigS: armS = False
        elif newHigh: armS, refL = True, l[i]
    return B, S


def table(df, tf, B, S, H, atr, nxt):
    h, l, c = df.high.values, df.low.values, df.close.values
    rows = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if i < 35 or not df.tradable.values[i]: continue
        end = min(i + HORIZON, nxt[i])
        if end <= i: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i]); risk = (c[i] - stop) * k
        if not risk > 0: continue
        rows.append([tf, i, k, risk, risk / atr[i - 1]] + outcome(h, l, c, i, k, stop, end))
    cols = ['tf', 'i', 'side', 'risk', 'risk_atr']
    for R in TARGETS: cols += [f'r{R:g}', f'x{R:g}']
    return add_context(pd.DataFrame(rows, columns=cols), df, tf, H)


def indep(g):
    aa = g.date < SPLIT; cells = []
    for R in (1.0, 2.0, 3.0):
        net = g[f'r{R:g}'] - COST / g.risk
        cells.append(f'{100 * (g[f"r{R:g}"] > 0).mean():4.1f}% {net.mean():+.3f}')
    net2 = g.r2 - COST / g.risk
    return f'{len(g):5d} | ' + ' | '.join(cells) + f' | {net2[aa].mean():+.3f} / {net2[~aa].mean():+.3f}'


if __name__ == '__main__':
    H = hourly()
    for tf in (1, 2):
        df = prepared('NQ', tf)
        nxt, atr = bar_context(df, tf)
        days = (df.datetime[df.tradable].dt.tz_convert('America/New_York') + pd.Timedelta(hours=6)).dt.date.astype(str).nunique()
        tabs = {}
        for name, (stage, el, on) in SETS.items():
            B, S = sigs(df, stage, el, on)
            if name == '(20,0,8,1)':
                B0, S0 = signals(df); assert (B == B0).all() and (S == S0).all()
            tabs[name] = table(df, tf, B, S, H, atr, nxt)
        base = tabs['(20,0,8,1)']
        print(f'\n################ {tf} 分 K')
        for name, t in tabs.items():
            same = len(set(t.i) & set(base.i))
            print(f'  {name}  {len(t):5d} 個訊號（{len(t) / days:4.1f}/天），停損中位數 {t.risk.median():.2f} 點，跟 (20,0,8,1) 同一根 K 的 {same} 個')
        print('\n  A. 訊號各自獨立：筆數 | 1R 勝率/淨 | 2R 勝率/淨 | 3R 勝率/淨 | 2R 淨 前段/後段')
        for gname, f in GROUPS:
            for name, t in tabs.items():
                print(f'    {gname:<16} {name:<12} {indep(t[f(t)])}')
        print('\n  B. EMA 開時會被擋掉的訊號（(20,0,8,0) 才有的）')
        off = tabs['(20,0,8,0)']; extra = off[~off.i.isin(base.i)]
        for gname, f in GROUPS:
            print(f'    {gname:<16} {indep(extra[f(extra)])}')
        print('\n  C. 一次一筆')
        for gname, f in GROUPS:
            if QUADRANT(gname): continue
            for name, t in tabs.items():
                sub = t[f(t)].sort_values('i')
                for R in ((1.0, 2.0, 3.0) if tf == 1 else (2.0,)):
                    print(f'    {gname:<16} {name:<12} {R:g}R  {fmt(stats(seq(sub, R), R, days))}')
        if tf == 1:
            print('\n  D. 逐月：TJ 順勢 + 1h 同向，一次一筆，2R，每筆淨 R')
            mm = {}
            for name, t in tabs.items():
                tt = seq(t[GROUPS[6][1](t)].sort_values('i'), 2.0)
                mm[name] = (tt.r2 - COST / tt.risk).groupby(tt.month).mean().round(3)
            m = pd.DataFrame(mm); print(m.to_string())
            print('  賺錢月份:', {k: int((v > 0).sum()) for k, v in m.items()})
