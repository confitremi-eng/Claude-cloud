import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, time
from bt import load, signals, simulate, summarize, atr
import trend as T
pd.set_option('display.width', 220)
for tf in (1, 2, 3, 5):
    t0 = time.time()
    df = load(tf)
    sig = signals(df)
    tr = simulate(df, sig)
    ctx = {'ema100slope': T.ema_slope(df, 100, 10), 'px>ema200': T.px_vs_ema(df, 200),
           'htf15': T.htf_ema(df, 15, 20), 'consensus': T.consensus(df)}
    print(f'===== {tf}-min: {len(df)} bars, {len(tr)} signals ({len(tr)/len(df)*100:.1f} per 100 bars)  [{time.time()-t0:.1f}s]')
    for col in ('R1.0', 'R1.5', 'R2.0', 'R3.0'):
        print(f'   all  {col}: {summarize(tr, col)}')
    for name, c in ctx.items():
        w = tr[c[tr.i.values] == tr.dir.values]; ag = tr[c[tr.i.values] == -tr.dir.values]
        print(f'   {name:12s} with-trend R1.5 {summarize(w)}   counter R1.5 {summarize(ag)}')
