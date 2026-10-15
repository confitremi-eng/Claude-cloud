import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd, itertools
from rbs import prepared, simulate
from fams import fam_bo, fam_breakout, fam_tjpull
START = pd.Timestamp('2026-04-03', tz='UTC')
def rth_mask(df):
    et = df.datetime.dt.tz_convert('America/New_York'); m = et.dt.hour * 60 + et.dt.minute
    return ((m >= 570) & (m < 960)).values
C = {
 'A  BO N=20 (現行組合)':        (fam_bo, dict(N=20), False),
 'B  BO N=20 + 只做美股盤中':      (fam_bo, dict(N=20), True),
 'C  BO N=20 + 強趨勢 + 盤中':     (fam_bo, dict(N=20, strong=True), True),
 'D  突破 N=20':                 (fam_breakout, dict(N=20), False),
 'E  突破 N=20 + 盤中':           (fam_breakout, dict(N=20), True),
 'F  突破 N=20 + 強趨勢 + 盤中':    (fam_breakout, dict(N=20, strong=True), True),
 'G  回測快線 + 盤中':             (fam_tjpull, dict(touch='fast'), True),
 'H  回測慢線 + 強趨勢 + 盤中':      (fam_tjpull, dict(touch='slow', strong=True), True),
 'I  BO N=8 淺回檔 + 盤中':         (fam_bo, dict(N=8), True),
}
rows = []
for sym in ('NQ', 'ES'):
    for tf in (1, 2, 3, 5):
        df = prepared(sym, tf); rth = rth_mask(df)
        mon = df.datetime.dt.tz_convert('America/New_York').dt.month.values
        for name, (fn, kw, only_rth) in C.items():
            sig = [s for s in fn(df, **kw) if df.datetime.iloc[s[0]] >= START and (not only_rth or rth[s[0]])]
            for R in (1.0, 1.5, 2.0):
                t = simulate(df, sig, sym, R=R)
                t['mon'] = mon[t.i.values] if len(t) else []
                for m, g in t.groupby('mon'):
                    if m == 9: continue
                    rows.append(dict(cand=name, R=R, sym=sym, tf=tf, mon=m, n=len(g), exp=g.R.mean(), win=100 * (g.R > 0).mean()))
M = pd.DataFrame(rows); M.to_csv('round2.csv', index=False)
pd.set_option('display.width', 250)
S = M.groupby(['cand', 'R']).apply(lambda x: pd.Series({
    'months+ (of 40)': int((x.exp > 0).sum()), 'cells': len(x),
    'mean exp (eq.wt)': x.exp.mean(), 'pooled exp': np.average(x.exp, weights=x.n),
    'win%': np.average(x.win, weights=x.n), 'trades': int(x.n.sum())})).reset_index()
print(S.sort_values('pooled exp', ascending=False).round(3).to_string(index=False))
