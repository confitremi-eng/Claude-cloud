import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from nqlab import Lab, day_limits
pd.set_option('display.width', 250)
labs = {tf: Lab('NQ', tf) for tf in (1, 2, 3, 5)}
ENTRY = {'G thr40 N30 ER.4': dict(N=30, thr=40.0, erMin=0.4), 'B thr50 N45 ER.4': dict(N=45, thr=50.0, erMin=0.4)}
EXIT = {'R2 h60 s10': dict(stopN=10, R=2.0, max_hold=60), 'trail30 s10': dict(stopN=10, R=0.0, max_hold=999, trail=30),
        'R3 h60 s20': dict(stopN=20, R=3.0, max_hold=60)}
LIM = {'no limit': (0, 0), 'max 1/day': (1, 0), 'max 2/day': (2, 0), 'stop after 1 loss': (0, 1), 'stop after 2 losses': (0, 2)}
rows = []
for en, ekw in ENTRY.items():
    for xn, xkw in EXIT.items():
        for ln, (mt, ml) in LIM.items():
            for tf, lab in labs.items():
                idx, dirs = lab.signals(**ekw)
                t = day_limits(lab.trades(idx, dirs, **xkw), mt, ml)
                for mo, g in t.groupby('month'):
                    rows.append(dict(entry=en, exit=xn, limit=ln, tf=tf, mon=mo, n=len(g), sumR=g.R.sum(), sumP=g.pts.sum()))
M = pd.DataFrame(rows); M['half'] = np.where(M.mon <= 6, 'AJ', 'JS')
def agg(x):
    n = x.n.sum(); aj = x[x.half == 'AJ']; js = x[x.half == 'JS']
    mm = x.groupby('mon').apply(lambda y: y.sumR.sum() / y.n.sum())
    return pd.Series({'n': n, 'avgR': x.sumR.sum() / n, 'pts': x.sumP.sum() / n, 'R_AJ': aj.sumR.sum() / aj.n.sum(),
                      'R_JS': js.sumR.sum() / js.n.sum(), 'n_JS': js.n.sum(), 'mon+': int((mm > 0).sum()),
                      'totR': x.sumR.sum(), 'totR_JS': js.sumR.sum()})
print(M.groupby(['entry', 'exit', 'limit'], sort=False).apply(agg).round(3).to_string())
