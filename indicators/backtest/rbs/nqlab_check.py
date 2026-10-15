import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import time, numpy as np, pandas as pd
from nqlab import Lab, summarize, SEL
from rbs import simulate
from round3 import variant
from round4 import er
# engine vs research simulator on the same C3 signals (research rule: warm=30 bars in block)
for tf in (1, 2, 3, 5):
    t0 = time.time()
    lab = Lab('NQ', tf)
    E = er(lab.df)
    ref = [s for s in variant(lab.df, 'NQ', N=30) if E[s[0]] > 0.4]
    t_ref = simulate(lab.df, ref, 'NQ', R=2.0)
    idx, dirs = lab.signals(N=30, thr=40, erLen=20, erMin=0.4)
    t_lab = lab.trades(idx, dirs, stopN=10, R=2.0, max_hold=60)
    a = set(zip(t_ref.i, t_ref.dir)); b = set(zip(t_lab.i, t_lab.dir))
    common = sorted(a & b)
    r1 = t_ref.set_index(['i', 'dir']).loc[common].R; r2 = t_lab.set_index(['i', 'dir']).loc[common].R
    print(f'NQ {tf}m: research n={len(t_ref)} avgR={t_ref.R.mean():+.3f} | lab n={len(t_lab)} avgR={t_lab.R.mean():+.3f} | '
          f'common {len(common)}, only research {len(a - b)}, only lab {len(b - a)}, same R on common: {np.mean(np.isclose(r1.values, r2.values)):.3f} ({time.time()-t0:.1f}s)')
