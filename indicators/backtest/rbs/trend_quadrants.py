"""Remi's Buy/Sell (current rule) split by Trend Judge state at the signal bar, vs all signals.

Trend Judge is estimated from 1-minute data (rbs.py: 5s / 15s EMA1130 as per-minute factors, diff
locked every 2 minutes). Trades: remi_export.py rules (stop = extreme of the signal bar and the one
before, entry at the signal close, fixed 1R / 2R, stop first if both hit, 60-bar time exit).
Net R subtracts COST points per trade.

usage: python3 trend_quadrants.py
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from rbs import prepared, COST, SPLIT
from remi_export import signals


def trades(df, B, S, horizon=60):
    h, l, c = df.high.values, df.low.values, df.close.values; out = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if i < 1 or i + 10 > len(c) - 1: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        end = min(len(c) - 1, i + horizon); res = []
        for R in (1.0, 2.0):
            tgt = c[i] + k * R * risk; r = None
            for j in range(i + 1, end + 1):
                if (l[j] <= stop) if k == 1 else (h[j] >= stop): r = -1.0; break
                if (h[j] >= tgt) if k == 1 else (l[j] <= tgt): r = R; break
            res.append((c[end] - c[i]) * k / risk if r is None else r)
        out.append((i, k, risk, *res))
    return pd.DataFrame(out, columns=['i', 'side', 'risk', 'r1', 'r2'])


GROUPS = [
    ('全部 Buy',          lambda t: t.side == 1),
    ('強UP + Buy',        lambda t: (t.side == 1) & (t.dir == 2)),
    ('UP + Buy',          lambda t: (t.side == 1) & (t.dir == 1)),
    ('MIX + Buy',         lambda t: (t.side == 1) & (t.dir == 0)),
    ('DOWN/強Down + Buy', lambda t: (t.side == 1) & (t.dir < 0)),
    ('全部 Sell',         lambda t: t.side == -1),
    ('強Down + Sell',     lambda t: (t.side == -1) & (t.dir == -2)),
    ('DOWN + Sell',       lambda t: (t.side == -1) & (t.dir == -1)),
    ('MIX + Sell',        lambda t: (t.side == -1) & (t.dir == 0)),
    ('UP/強UP + Sell',    lambda t: (t.side == -1) & (t.dir > 0)),
    ('全部訊號',          lambda t: t.side != 0),
    ('四象限合計 (順勢)', lambda t: t.side * t.dir > 0),
    ('強勢兩象限',        lambda t: t.side * t.dir == 2),
    ('MIX',               lambda t: t.dir == 0),
    ('逆勢',              lambda t: t.side * t.dir < 0),
]


def row(name, t, cost):
    if len(t) == 0:
        return f'{name:<18} {0:5d}'
    net1 = t.r1 - cost / t.risk
    se = t.r1.std(ddof=1) / np.sqrt(len(t)) if len(t) > 1 else np.nan
    a, b = t[t.early], t[~t.early]
    return (f'{name:<18} {len(t):5d}  {100 * (t.r1 > 0).mean():5.1f}%  {t.r1.mean():+.3f} ±{se:.3f}  {net1.mean():+.3f}  '
            f'{100 * (t.r2 > 0).mean():5.1f}%  {t.r2.mean():+.3f}  |  {a.r1.mean() if len(a) else np.nan:+.3f} ({len(a):4d})  '
            f'{b.r1.mean() if len(b) else np.nan:+.3f} ({len(b):4d})')


for sym in ('NQ', 'ES'):
    for tf in (1, 2):
        df = prepared(sym, tf)
        B, S = signals(df)
        t = trades(df, B, S)
        t = t[df.tradable.values[t.i]].reset_index(drop=True)
        t['dir'] = df.tj_dir.values[t.i]
        t['early'] = (df.datetime.values[t.i] < SPLIT.to_datetime64())
        print(f'\n=== {sym} {tf}m  ({df.datetime[df.tradable].iloc[0]:%m/%d} .. {df.datetime.iloc[-1]:%m/%d}, 全天, '
              f'成本 {COST[sym]} 點, 停損中位數 {t.risk.median():.2f})')
        print(f'{"":<18} {"筆數":>5}  {"1R勝率":>6}  {"1R平均 ±標準誤":>14}  {"扣成本":>6}  {"2R勝率":>6}  {"2R平均":>6}  |  '
              f'{"前段2-6月":>13}  {"後段7-9月":>13}')
        for name, f in GROUPS:
            print(row(name, t[f(t)], COST[sym]))
            if name in ('DOWN/強Down + Buy', 'UP/強UP + Sell'):
                print()
