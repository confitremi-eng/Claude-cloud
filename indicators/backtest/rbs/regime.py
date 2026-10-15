import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rbs import prepared, simulate, stats
from fams import fam_bo, fam_breakout, fam_tjpull
START = pd.Timestamp('2026-04-03', tz='UTC')
def month_table(name, fn, kw, ekw):
    out = []
    for sym in ('NQ', 'ES'):
        for tf in (1, 3, 5):
            df = prepared(sym, tf)
            sig = [s for s in fn(df, **kw) if df.datetime.iloc[s[0]] >= START]
            t = simulate(df, sig, sym, **ekw)
            et = t.time.dt.tz_convert('America/New_York'); m = et.dt.hour * 60 + et.dt.minute
            t['rth'] = (m >= 570) & (m < 960); t['mon'] = et.dt.month
            t['sym'] = sym; t['tf'] = tf
            out.append(t)
    T = pd.concat(out)
    piv = T[T.rth].groupby(['sym', 'mon']).R.agg(['mean', 'size']).round(3)
    on = T[~T.rth].groupby(['sym']).R.agg(['mean', 'size']).round(3)
    print(f'=== {name}: RTH trades, expectancy by month (1/3/5m pooled)')
    print(piv.unstack('sym').to_string())
    print('   overnight trades (full-session days only):', on.to_dict('index'))
month_table('Breakout N=20 in TJ trend, 2R', fam_breakout, dict(N=20), dict(R=2.0))
month_table('BO N=20 in TJ trend (current combo), 1.5R', fam_bo, dict(N=20), dict(R=1.5))
