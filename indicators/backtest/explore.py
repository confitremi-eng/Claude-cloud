import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, itertools, time
from bt import load
import trend as T
from families import fam_reversal, fam_pullback, fam_breakout, fam_ema_pullback, trade, stats
SPLIT = pd.Timestamp('2026-07-01', tz='UTC')
rows = []
for tf in (1, 3, 5):
    df = load(tf)
    trends = {'px>ema200': T.px_vs_ema(df, 200), 'ema50>200': T.ema_cross(df, 50, 200),
              'slope100': T.ema_slope(df, 100, 10), 'htf15': T.htf_ema(df, 15, 20), 'htf60': T.htf_ema(df, 60, 20)}
    fams = {}
    for tn, tr in trends.items():
        for N in (5, 8, 13):
            fams[f'pullback N={N} | {tn}'] = fam_pullback(df, N=N, trend=tr)
        for N in (20, 40):
            fams[f'breakout N={N} | {tn}'] = fam_breakout(df, N=N, trend=tr)
        fams[f'emaPB20 | {tn}'] = fam_ema_pullback(df, 20, trend=tr)
    fams['reversal N=20 | none'] = fam_reversal(df, 20)
    for name, sigs in fams.items():
        for ex, kw in (('R1.5', dict(exit='R', R=1.5)), ('R2', dict(exit='R', R=2.0)), ('chand3', dict(exit='chand', k=3.0))):
            t = trade(df, sigs, **kw)
            tr_, te_ = t[t.time < SPLIT], t[t.time >= SPLIT]
            a, b = stats(tr_), stats(te_)
            rows.append(dict(tf=tf, sig=name, exit=ex, n_tr=a.get('n'), exp_tr=a.get('expR'), pf_tr=a.get('pf'),
                             n_te=b.get('n'), exp_te=b.get('expR'), pf_te=b.get('pf')))
R = pd.DataFrame(rows)
R.to_csv('explore.csv', index=False)
pd.set_option('display.width', 220); pd.set_option('display.max_rows', 400)
good = R[(R.exp_tr > 0) & (R.exp_te > 0)].sort_values(['tf', 'exp_te'], ascending=[True, False])
print('configs positive in BOTH train (Apr-Jun) and test (Jul-Sep):'); print(good.to_string(index=False))
print('\nbest by family (min of train/test expectancy):')
R['minexp'] = R[['exp_tr', 'exp_te']].min(axis=1)
R['family'] = R.sig.str.split(' ').str[0]
print(R.sort_values('minexp', ascending=False).groupby(['tf', 'family']).head(2).sort_values(['tf', 'minexp'], ascending=[True, False]).to_string(index=False))
