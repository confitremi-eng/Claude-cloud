import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rbs import prepared
for sym in ('NQ', 'ES'):
    for tf in (1, 5):
        df = prepared(sym, tf)
        df = df[df.datetime >= pd.Timestamp('2026-04-03', tz='UTC')]
        share = df.tj_dir.value_counts(normalize=True).reindex([2, 1, 0, -1, -2]).fillna(0) * 100
        et = df.datetime.dt.tz_convert('America/New_York'); m = et.dt.hour * 60 + et.dt.minute
        rth = (m >= 570) & (m < 960)
        print(f'{sym} {tf}m: share % 強UP {share[2]:.1f} UP {share[1]:.1f} MIX {share[0]:.1f} DOWN {share[-1]:.1f} 強Down {share[-2]:.1f} | '
              f'|diff| median {np.nanmedian(np.abs(df.tj_diff)):.1f}  p90 {np.nanpercentile(np.abs(df.tj_diff), 90):.1f} | '
              f'trend share RTH {100*(df.tj_dir[rth] != 0).mean():.1f}% vs other {100*(df.tj_dir[~rth] != 0).mean():.1f}%')
