import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, itertools, time
from rbs import prepared, simulate, stats, SPLIT
from fams import fam_bo, fam_tjpull, fam_breakout
START = pd.Timestamp('2026-04-03', tz='UTC')
CELLS = [(s, t) for s in ('NQ', 'ES') for t in (1, 2, 3, 5)]
variants = {}
for N, eo, st in itertools.product((5, 8, 13, 20, 25), (True, False), (False, True)):
    variants[f'BO N={N} ema={int(eo)} strong={int(st)}'] = (fam_bo, dict(N=N, ema_on=eo, strong=st))
for st, touch, trig in itertools.product((False, True), ('fast', 'slow'), ('swingbar', 'prevbar')):
    variants[f'TJpull {touch} trig={trig} strong={int(st)}'] = (fam_tjpull, dict(strong=st, touch=touch, trig=trig))
for N, st in itertools.product((10, 20, 40), (False, True)):
    variants[f'Breakout N={N} strong={int(st)}'] = (fam_breakout, dict(N=N, stopN=10, strong=st))
exits = {'1R': dict(R=1.0), '1.5R': dict(R=1.5), '2R': dict(R=2.0), '2R+trendexit': dict(R=2.0, trend_exit=True),
         'trendexit only': dict(R=99.0, trend_exit=True, hold=120)}
rows = []
t0 = time.time()
for (sym, tf) in CELLS:
    df = prepared(sym, tf)
    for vname, (fn, kw) in variants.items():
        sig = [s for s in fn(df, **kw) if df.datetime.iloc[s[0]] >= START]
        for ename, ekw in exits.items():
            t = simulate(df, sig, sym, **ekw)
            a, b = stats(t[t.time < SPLIT]), stats(t[t.time >= SPLIT])
            rows.append(dict(sym=sym, tf=tf, var=vname, exit=ename, n_tr=a['n'], exp_tr=a['expR'], win_tr=a['win'],
                             n_te=b['n'], exp_te=b['expR'], win_te=b['win']))
    print(f'done {sym} {tf}m  [{time.time()-t0:.0f}s]', flush=True)
R = pd.DataFrame(rows); R.to_csv('round1.csv', index=False)
