import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rbs import prepared, bo_signals, simulate, stats, SPLIT
START = pd.Timestamp('2026-04-03', tz='UTC')
def fmt(s): return f"n={s['n']:4d} win={s['win']:5.1f}% expR={s['expR']:+.3f} PF={s['pf']:.2f}" if s['n'] else 'n=0'
rows = []
for N in (25, 20):
    print(f'######## stage N={N}  (target 1.5R, stop = swing bar extreme, max 60 bars)')
    for sym in ('NQ', 'ES'):
        for tf in (1, 2, 3, 5):
            df = prepared(sym, tf)
            sig = [s for s in bo_signals(df, N=N) if df.datetime.iloc[s[0]] >= START]
            td = df.tj_dir.values
            groups = {'with': [s for s in sig if td[s[0]] * s[1] >= 1],
                      'counter': [s for s in sig if td[s[0]] * s[1] <= -1],
                      'MIX': [s for s in sig if td[s[0]] == 0]}
            line = f'{sym} {tf}m '
            for g, ss in groups.items():
                t = simulate(df, ss, sym, R=1.5)
                st = stats(t); tr = stats(t[t.time < SPLIT]); te = stats(t[t.time >= SPLIT])
                rows.append(dict(N=N, sym=sym, tf=tf, grp=g, **st, exp_tr=tr['expR'], exp_te=te['expR']))
                line += f'| {g}: {fmt(st)} '
            print(line)
R = pd.DataFrame(rows); R.to_csv('baseline.csv', index=False)
print('\nwith-trend only, train vs test expectancy:')
print(R[R.grp == 'with'][['N', 'sym', 'tf', 'n', 'win', 'expR', 'exp_tr', 'exp_te', 'pf']].round(3).to_string(index=False))
