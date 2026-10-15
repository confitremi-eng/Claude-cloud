import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from nqlab import Lab
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 500)
# all trend breakouts (N30, diff>40, no ER filter) so the buckets have room
rows = []
for tf in (1, 2, 3, 5):
    lab = Lab('NQ', tf)
    idx, dirs = lab.signals(N=30, thr=40.0, erMin=0.0)
    t = lab.trades(idx, dirs, stopN=10, R=2.0, max_hold=60)
    t['tf'] = tf
    t['hour'] = lab.mins[t.i.values] // 60 + (lab.mins[t.i.values] % 60 >= 30) * 0.5
    t['absdiff'] = np.abs(lab.diff[t.i.values])
    t['er'] = lab.roll('er', 20)[t.i.values]
    t['risk_atr'] = t.risk / lab.atr[t.i.values]
    rows.append(t)
T = pd.concat(rows)
T['half'] = np.where(T.month <= 6, 'Apr-Jun', 'Jul-Sep')
def tab(col, bins=None, labels=None):
    x = T.copy()
    x['b'] = pd.cut(x[col], bins=bins, labels=labels, right=False) if bins is not None else x[col]
    g = x.groupby(['b', 'half'], observed=True).R.agg(['count', 'mean']).unstack('half')
    g[('all', 'n')] = x.groupby('b', observed=True).R.count(); g[('all', 'avgR')] = x.groupby('b', observed=True).R.mean()
    g[('all', 'pts')] = x.groupby('b', observed=True).pts.mean()
    print(f'\n== by {col}'); print(g.round(3).to_string())
tab('hour', bins=[9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5], labels=['10:00-10:59*', '11:00-11:59*', '12:00', '13:00', '14:00', '15:00', '15:30+'])
tab('absdiff', bins=[40, 50, 60, 80, 100, 150, 1e9])
tab('er', bins=[0, 0.2, 0.3, 0.4, 0.5, 0.6, 1.01])
tab('risk_atr', bins=[0, 2, 3, 4, 5, 100])
tab('tf')
tab('month')
