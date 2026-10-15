import sys, os, itertools, time; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from nqlab import Lab
t0 = time.time()
labs = {tf: Lab('NQ', tf) for tf in (1, 2, 3, 5)}
# how concentrated are the very-strong-trend trades?
for tf, lab in labs.items():
    idx, dirs = lab.signals(N=30, thr=150.0, erMin=0.0)
    print(f'{tf}m diff>150 signals: {len(idx)} on {len(set(lab.day[idx]))} days')
EXITS = {'R2 h60': dict(R=2.0, max_hold=60), 'R3 h60': dict(R=3.0, max_hold=60), 'time60': dict(R=0.0, max_hold=60),
         'trail20': dict(R=0.0, max_hold=999, trail=20), 'trail30': dict(R=0.0, max_hold=999, trail=30)}
grid = list(itertools.product((40.0, 50.0, 60.0, 80.0, 100.0), (30, 45, 60), (0.0, 0.4, 0.5), tuple(EXITS), (10, 20), (0, 10, 20)))
rows = []
for thr, N, erm, ex, sN, bias in grid:
    for tf, lab in labs.items():
        idx, dirs = lab.signals(N=N, thr=thr, erMin=erm, bias=bias)
        t = lab.trades(idx, dirs, stopN=sN, **EXITS[ex])
        if not len(t):
            continue
        g = t.groupby('month').agg(n=('R', 'size'), sumR=('R', 'sum'), sumP=('pts', 'sum'), wins=('R', lambda r: int((r > 0).sum())))
        for mo, r in g.iterrows():
            rows.append((thr, N, erm, ex, sN, bias, tf, int(mo), int(r.n), r.sumR, r.sumP, int(r.wins)))
M = pd.DataFrame(rows, columns=['thr', 'N', 'erMin', 'exit', 'stopN', 'bias', 'tf', 'mon', 'n', 'sumR', 'sumP', 'wins'])
M.to_csv('nq_stage2.csv', index=False)
print(f'{len(grid)} combos x 4 TF in {time.time()-t0:.0f}s')
