import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Frozen candidates on the selection period (2026-04-03 .. 09-01) and the untouched holdout (2026-02-04 .. 03-31)."""
import numpy as np, pandas as pd
from nqlab import Lab, SEL, HOLD
from rbs import bo_signals, simulate

# trend thresholds are in index points: the generic rule uses Trend Judge's strong level (NQ 40, ES 8);
# B and C are the NQ-only candidates from the NQ study (thresholds scaled by the same factor for ES).
STRONG = {'NQ': 40.0, 'ES': 8.0}
CANDS = {
    'G  通用：N30 強趨勢 ER>0.4，2R': (dict(N=30, k=1.0, erMin=0.4), dict(stopN=10, R=2.0, max_hold=60)),
    'G-trail 同上，30 根通道出場': (dict(N=30, k=1.0, erMin=0.4), dict(stopN=10, R=0.0, max_hold=999, trail=30)),
    'B-trail N45 強趨勢x1.25 ER>0.4，30 根通道': (dict(N=45, k=1.25, erMin=0.4), dict(stopN=10, R=0.0, max_hold=999, trail=30)),
    'C  強趨勢x2.5 無ER，30 根通道': (dict(N=30, k=2.5, erMin=0.0), dict(stopN=10, R=0.0, max_hold=999, trail=30)),
}


def baseline(lab, period):
    df = lab.df
    td = df.tj_dir.values
    t0, t1 = period
    sig = [s for s in bo_signals(df, N=25) if t0 <= df.datetime.iloc[s[0]] < t1 and td[s[0]] * s[1] >= 1]
    t = simulate(df, sig, lab.sym, R=2.0)
    t['month'] = lab.month[t.i.values] if len(t) else []
    return t


rows = []
for sym in ('NQ', 'ES'):
    for tf in (1, 2, 3, 5):
        lab = Lab(sym, tf)
        for pname, period in (('選參數 4/3-9/1', SEL), ('保留 2/4-3/31', HOLD)):
            res = {'0 現行 買賣訊號(25)+TJ': baseline(lab, period)}
            for cn, (skw, xkw) in CANDS.items():
                skw = dict(skw)
                skw['thr'] = STRONG[sym] * skw.pop('k')
                idx, dirs = lab.signals(period=period, **skw)
                res[cn] = lab.trades(idx, dirs, **xkw)
            for cn, t in res.items():
                for mo, g in t.groupby('month'):
                    rows.append(dict(sym=sym, tf=tf, period=pname, cand=cn, mon=int(mo), n=len(g), sumR=g.R.sum(),
                                     sumP=g.pts.sum(), wins=int((g.R > 0).sum())))
M = pd.DataFrame(rows)
M.to_csv('holdout.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400)


def agg(x):
    n = x.n.sum()
    return pd.Series({'n': n, 'win%': 100 * x.wins.sum() / n, 'avgR': x.sumR.sum() / n, 'pts/tr': x.sumP.sum() / n})


for sym in ('NQ', 'ES'):
    X = M[M.sym == sym]
    print(f'\n######## {sym}: pooled over 1/2/3/5m')
    print(X.groupby(['cand', 'period'], sort=False).apply(agg).unstack('period').round(3).to_string())
    print(f'\n{sym} holdout by timeframe (avgR / n):')
    H = X[X.period == '保留 2/4-3/31'].groupby(['cand', 'tf'], sort=False).apply(lambda x: f"{x.sumR.sum() / x.n.sum():+.3f} ({x.n.sum()})")
    print(H.unstack('tf').to_string())
    print(f'\n{sym} holdout by month (avgR / n):')
    H = X[X.period == '保留 2/4-3/31'].groupby(['cand', 'mon'], sort=False).apply(lambda x: f"{x.sumR.sum() / x.n.sum():+.3f} ({x.n.sum()})")
    print(H.unstack('mon').to_string())
