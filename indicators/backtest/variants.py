import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from bt import load
from families import fam_reversal, trade, stats
SPLIT = pd.Timestamp('2026-07-01', tz='UTC')
V = {
 'v3 default (N20, EMA8 hl2, 1.5R)':      (dict(N=20), dict(exit='R', R=1.5)),
 'no EMA filter':                          (dict(N=20, ema_on=False), dict(exit='R', R=1.5)),
 'EMA source close':                       (dict(N=20, src='close'), dict(exit='R', R=1.5)),
 'N=30':                                   (dict(N=30), dict(exit='R', R=1.5)),
 'N=40':                                   (dict(N=40), dict(exit='R', R=1.5)),
 'N=10':                                   (dict(N=10), dict(exit='R', R=1.5)),
 'retrigger allowed (no consume)':         (dict(N=20, consume=False), dict(exit='R', R=1.5)),
 'wait <= 10 bars':                        (dict(N=20, max_wait=10), dict(exit='R', R=1.5)),
 'min stop 1.0 ATR':                       (dict(N=20), dict(exit='R', R=1.5, min_risk=1.0)),
 'target 1R':                              (dict(N=20), dict(exit='R', R=1.0)),
 'target 2R':                              (dict(N=20), dict(exit='R', R=2.0)),
 'target 3R':                              (dict(N=20), dict(exit='R', R=3.0)),
}
rows = []
for tf in (1, 2, 3, 5):
    df = load(tf)
    for name, (sk, tk) in V.items():
        t = trade(df, fam_reversal(df, **sk), warm=5, **tk)
        for half, part in (('tr', t[t.time < SPLIT]), ('te', t[t.time >= SPLIT])):
            s = stats(part); rows.append(dict(var=name, tf=tf, half=half, n=s.get('n'), exp=s.get('expR')))
R = pd.DataFrame(rows)
P = R.pivot_table(index='var', columns=['tf', 'half'], values='exp')
P['mean'] = P.mean(axis=1); P['pos_cells'] = (P.drop(columns='mean') > 0).sum(axis=1)
N = R.pivot_table(index='var', columns='tf', values='n', aggfunc='sum')
pd.set_option('display.width', 250)
print(P.round(3).sort_values('mean', ascending=False).to_string())
print('\ntrades per variant (train+test) by timeframe:'); print(N.to_string())
