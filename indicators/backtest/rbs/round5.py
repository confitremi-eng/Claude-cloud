import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Round 5: R-multiples vs fixed-contract points. Does the stop width explain the gap, and does a
max-risk rule (skip or cap wide stops) fix fixed-contract P&L without hurting R?"""
import numpy as np, pandas as pd
from rbs import prepared, simulate, atr, SPLIT
from round3 import variant
from round4 import er

def c3(df, sym):
    E = er(df)
    return [s for s in variant(df, sym, N=30) if E[s[0]] > 0.4]

pd.set_option('display.width', 250); pd.set_option('display.max_rows', 400)
rows = []; buck = []
for sym in ('NQ', 'ES'):
    for tf in (1, 2, 3, 5):
        df = prepared(sym, tf)
        A = atr(df.high.values, df.low.values, df.close.values, 14)
        mon = df.datetime.dt.tz_convert('America/New_York').dt.month.values
        sig = c3(df, sym)
        t = simulate(df, sig, sym, R=2.0)
        t['ratio'] = t.risk / A[t.i.values]
        t['mon'] = mon[t.i.values]
        q = pd.qcut(t.ratio, 4, labels=['Q1窄', 'Q2', 'Q3', 'Q4寬'])
        for b, g in t.groupby(q, observed=True):
            buck.append(dict(sym=sym, tf=tf, bucket=b, n=len(g), ratio=g.ratio.median(), risk_pts=g.risk.median(),
                             win=100 * (g.R > 0).mean(), avgR=g.R.mean(), avg_pts=g.pts.mean()))
        for k in (None, 1.5, 2.0, 2.5, 3.0, 4.0):
            for mode in (('skip', 'cap') if k else ('none',)):
                if mode == 'skip':
                    keep = [s for s in sig if (df.close.values[s[0]] - (s[2] - s[1] * 0.25)) * s[1] <= k * A[s[0]]]
                    tt = simulate(df, keep, sym, R=2.0)
                elif mode == 'cap':
                    cl = df.close.values
                    capped = []
                    for i, d, sw in sig:
                        stop = sw - d * 0.25
                        if (cl[i] - stop) * d > k * A[i]:
                            sw = cl[i] - d * k * A[i] + d * 0.25
                        capped.append((i, d, sw))
                    tt = simulate(df, capped, sym, R=2.0)
                else:
                    tt = t
                tt = tt.copy(); tt['mon'] = mon[tt.i.values] if len(tt) else []
                wp = tt.pts[tt.pts > 0].sum(); lp = -tt.pts[tt.pts < 0].sum()
                rows.append(dict(rule=f'{mode} {k}' if k else 'C3', sym=sym, tf=tf, n=len(tt), win=100 * (tt.R > 0).mean(),
                                 avgR=tt.R.mean(), avg_pts=tt.pts.mean(), tot_pts=tt.pts.sum(), pf_pts=wp / lp if lp else np.inf,
                                 mpos_pts=sum(1 for mo, g in tt.groupby('mon') if mo != 9 and g.pts.sum() > 0),
                                 R_tr=tt[tt.time < SPLIT].R.mean(), R_te=tt[tt.time >= SPLIT].R.mean(),
                                 pts_tr=tt[tt.time < SPLIT].pts.mean(), pts_te=tt[tt.time >= SPLIT].pts.mean()))
B = pd.DataFrame(buck); F = pd.DataFrame(rows)
F.to_csv('round5.csv', index=False)
print('== C3 trades at 2R bucketed by stop width (risk / ATR14) ==')
print(B.round(2).to_string(index=False))
print('\n== max-risk rules, per cell ==')
print(F.round(3).to_string(index=False))
print('\n== pooled ==')
P = F.groupby('rule').apply(lambda x: pd.Series({'trades': int(x.n.sum()), 'win%': np.average(x.win, weights=x.n),
    'avgR': np.average(x.avgR, weights=x.n), 'R cells+': int((x.avgR > 0).sum()), 'pts cells+': int((x.tot_pts > 0).sum()),
    'R_te': np.average(x.R_te.fillna(0), weights=x.n), 'NQ pts/trade': np.average(x[x.sym == 'NQ'].avg_pts, weights=x[x.sym == 'NQ'].n),
    'ES pts/trade': np.average(x[x.sym == 'ES'].avg_pts, weights=x[x.sym == 'ES'].n)}))
print(P.round(3).to_string())
