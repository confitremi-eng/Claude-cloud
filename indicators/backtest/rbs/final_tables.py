import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""Per symbol x timeframe tables on the clean data: current combination vs Remi's Buy/Sell (generic rule, 2R)."""
import numpy as np, pandas as pd
from nqlab import Lab
from rbs import bo_signals, simulate

ALL = (pd.Timestamp('2026-02-02', tz='UTC'), pd.Timestamp('2026-09-02', tz='UTC'))
STRONG = {'NQ': 40.0, 'ES': 8.0}
PER = {2: '2-3月', 3: '2-3月', 4: '4-6月', 5: '4-6月', 6: '4-6月', 7: '7-9月', 8: '7-9月', 9: '7-9月'}
rows = []
for sym in ('NQ', 'ES'):
    for tf in (1, 2, 3, 5):
        lab = Lab(sym, tf)
        df = lab.df
        td = df.tj_dir.values
        sig = [s for s in bo_signals(df, N=25) if ALL[0] <= df.datetime.iloc[s[0]] < ALL[1] and td[s[0]] * s[1] >= 1]
        tb = simulate(df, sig, sym, R=2.0)
        tb['month'] = lab.month[tb.i.values]
        idx, dirs = lab.signals(N=30, thr=STRONG[sym], erMin=0.4, period=ALL)
        for R in (1.0, 1.5, 2.0):
            tg = lab.trades(idx, dirs, stopN=10, R=R, max_hold=60)
            for name, t in (('現行', tb), ('Remi', tg)):
                if name == '現行' and R != 2.0:
                    continue
                for _, r in t.iterrows():
                    rows.append((sym, tf, name, R, PER[int(r.month)], r.R, r.pts, getattr(r, 'kind', np.nan), r.risk))
T = pd.DataFrame(rows, columns=['sym', 'tf', 'cand', 'tgt', 'per', 'R', 'pts', 'kind', 'risk'])
T.to_csv('final_tables_trades.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)


def agg(x):
    return pd.Series({'n': len(x), 'win%': 100 * (x.R > 0).mean(), 'avgR': x.R.mean(), 'pts': x.pts.mean()})


M = T[T.tgt == 2.0]
print('== 2R, all 7 months')
print(M.groupby(['sym', 'tf', 'cand']).apply(agg).unstack('cand').round(3).to_string())
print('\n== 2R, avgR (n) by period')
print(M.groupby(['sym', 'tf', 'cand', 'per']).apply(lambda x: f'{x.R.mean():+.3f} ({len(x)})').unstack('per').to_string())
print('\n== 2R pooled by symbol and period')
print(M.groupby(['sym', 'cand', 'per']).apply(agg).round(3).to_string())
print(M.groupby(['sym', 'cand']).apply(agg).round(3).to_string())
print('\n== Remi win% / avgR by target, all 7 months')
G = T[T.cand == 'Remi']
print(G.groupby(['sym', 'tf', 'tgt']).apply(lambda x: f'{100 * (x.R > 0).mean():.1f}% ({x.R.mean():+.3f})').unstack('tgt').to_string())
print(G.groupby(['sym', 'tgt']).apply(agg).round(3).to_string())
print('\n== Remi 2R exits (stop / target / time) and median stop in points')
R2 = G[G.tgt == 2.0]
print(R2.groupby(['sym', 'tf']).apply(lambda x: pd.Series({'target%': 100 * (x.kind == 1).mean(), 'stop%': 100 * (x.kind == -1).mean(),
      'time%': 100 * (x.kind == 2).mean(), 'med_stop': x.risk.median()})).round(1).to_string())
