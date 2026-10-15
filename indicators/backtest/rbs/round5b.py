import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Round 5b: same clock-time lookback on every timeframe (breakout window / stop window in minutes)."""
import numpy as np, pandas as pd
from rbs import prepared, simulate, SPLIT
from round3 import variant
from round4 import er

pd.set_option('display.width', 250)
rows = []
for sym in ('NQ', 'ES'):
    for tf in (1, 2, 3, 5):
        df = prepared(sym, tf)
        E = er(df)
        mon = df.datetime.dt.tz_convert('America/New_York').dt.month.values
        tests = {'C3 (N30 stop10)': (30, 10)}
        if tf == 1:
            tests.update({'1m N45': (45, 10), '1m N60': (60, 10), '1m N60 stop20': (60, 20), '1m N30 stop20': (30, 20)})
        for vn, (N, sN) in tests.items():
            sig = [s for s in variant(df, sym, N=N, stopN=sN) if E[s[0]] > 0.4]
            t = simulate(df, sig, sym, R=2.0)
            t['mon'] = mon[t.i.values]
            rows.append(dict(var=vn, sym=sym, tf=tf, n=len(t), win=100 * (t.R > 0).mean(), avgR=t.R.mean(),
                             pts_trade=t.pts.mean(), mpos=sum(1 for mo, g in t.groupby('mon') if mo != 9 and g.R.mean() > 0),
                             R_tr=t[t.time < SPLIT].R.mean(), R_te=t[t.time >= SPLIT].R.mean()))
print(pd.DataFrame(rows).round(3).to_string(index=False))
