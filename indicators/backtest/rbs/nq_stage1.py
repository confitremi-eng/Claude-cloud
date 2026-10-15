import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from nqlab import Lab
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
BASE_S = dict(N=30, thr=40.0, erLen=20, erMin=0.4, adxMin=0.0, skip=0, stop_at=960, side=0)
BASE_X = dict(stopN=10, atrK=0.0, R=2.0, max_hold=60, trail=0, be_at=0.0)
V = {'base': ({}, {})}
for N in (10, 15, 20, 45, 60): V[f'N={N}'] = ({'N': N}, {})
for thr in (20, 30, 50, 60, 80): V[f'thr={thr}'] = ({'thr': float(thr)}, {})
for e in (0.0, 0.3, 0.5, 0.6): V[f'ER>{e}'] = ({'erMin': e}, {})
for L in (10, 30): V[f'ERlen={L}'] = ({'erLen': L}, {})
for a in (20, 25, 30): V[f'ADX>{a} (no ER)'] = ({'erMin': 0.0, 'adxMin': float(a)}, {})
for s in (60, 120, 180): V[f'skip {s}min'] = ({'skip': s}, {})
for e in (900, 840, 720): V[f'no entry after {e//60}:{e%60:02d}'] = ({'stop_at': e}, {})
for sn in (5, 15, 20): V[f'stopN={sn}'] = ({}, {'stopN': sn})
for k in (1.0, 1.5, 2.0, 3.0): V[f'ATR stop {k}'] = ({}, {'atrK': k})
for R in (1.0, 1.5, 3.0, 0.0): V[f'R={R}'] = ({}, {'R': R})
for mh in (30, 120, 999): V[f'hold {mh}'] = ({}, {'max_hold': mh})
for tr in (10, 20, 30): V[f'trail {tr}'] = ({}, {'trail': tr})
for tr in (20,): V[f'trail {tr} no target'] = ({}, {'trail': tr, 'R': 0.0, 'max_hold': 999})
V['breakeven at 1R'] = ({}, {'be_at': 1.0})
V['long only'] = ({'side': 1}, {}); V['short only'] = ({'side': -1}, {})
rows = []
labs = {tf: Lab('NQ', tf) for tf in (1, 2, 3, 5)}
for name, (s_kw, x_kw) in V.items():
    for tf, lab in labs.items():
        sk = {**BASE_S, **s_kw}
        idx, dirs = lab.signals(**sk)
        t = lab.trades(idx, dirs, **{**BASE_X, **x_kw})
        for mo, g in t.groupby('month'):
            rows.append(dict(var=name, tf=tf, mon=int(mo), n=len(g), sumR=g.R.sum(), sumP=g.pts.sum(), wins=int((g.R > 0).sum())))
M = pd.DataFrame(rows); M.to_csv('nq_stage1.csv', index=False)
M['half'] = np.where(M.mon <= 6, 'AJ', 'JS')
def agg(x):
    n = x.n.sum()
    out = {'trades': n, 'win%': 100 * x.wins.sum() / n, 'avgR': x.sumR.sum() / n, 'pts/tr': x.sumP.sum() / n}
    for h in ('AJ', 'JS'):
        y = x[x.half == h]; out[f'R_{h}'] = y.sumR.sum() / max(y.n.sum(), 1)
    for tf in (1, 2, 3, 5):
        y = x[x.tf == tf]; out[f'R_{tf}m'] = y.sumR.sum() / max(y.n.sum(), 1)
    mm = x.groupby('mon').apply(lambda y: y.sumR.sum() / y.n.sum())
    out['mon+'] = f"{int((mm > 0).sum())}/{len(mm)}"
    out['worst_mon'] = mm.min()
    return pd.Series(out)
S = M.groupby('var', sort=False).apply(agg)
print(S.round(3).to_string())
