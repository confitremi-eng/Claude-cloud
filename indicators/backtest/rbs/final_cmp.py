import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rbs import prepared, simulate, bo_signals, SPLIT
from round3 import variant
from round4 import adx, er
START = pd.Timestamp('2026-04-03', tz='UTC')
def candidates(df, sym):
    A = adx(df); E = er(df)
    n30 = variant(df, sym, N=30); n40 = variant(df, sym, N=40)
    td = df.tj_dir.values
    base = [s for s in bo_signals(df, N=25) if df.datetime.iloc[s[0]] >= START and td[s[0]] * s[1] >= 1]
    return {'0 現行：買賣訊號(25)+TJ趨勢': base,
            'C1 突破N30+強趨勢+盤中': n30,
            'C2 C1+ADX>25': [s for s in n30 if A[s[0]] > 25],
            'C3 C1+ER>0.4': [s for s in n30 if E[s[0]] > 0.4],
            'C4 突破N40+強趨勢+盤中+ADX>25': [s for s in n40 if A[s[0]] > 25]}
rows = []
for sym in ('NQ', 'ES'):
    for tf in (1, 2, 3, 5):
        df = prepared(sym, tf)
        mon = df.datetime.dt.tz_convert('America/New_York').dt.month.values
        for cn, sig in candidates(df, sym).items():
            for R in (1.0, 1.5, 2.0):
                t = simulate(df, sig, sym, R=R)
                t['mon'] = mon[t.i.values] if len(t) else []
                w = t.R[t.R > 0].sum(); L = -t.R[t.R < 0].sum()
                mpos = sum(1 for mo, g in t.groupby('mon') if mo != 9 and g.R.mean() > 0)
                rows.append(dict(cand=cn, sym=sym, tf=tf, R=R, n=len(t), win=100 * (t.R > 0).mean(), exp=t.R.mean(),
                                 pf=w / L if L else np.inf, pts=t.pts.sum(), months_pos=mpos,
                                 exp_tr=t[t.time < SPLIT].R.mean(), exp_te=t[t.time >= SPLIT].R.mean()))
F = pd.DataFrame(rows); F.to_csv('final_cmp.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
for R in (2.0, 1.5, 1.0):
    print(f'\n===== target {R}R')
    print(F[F.R == R].pivot_table(index=['cand'], columns=['sym', 'tf'], values='exp').round(3).to_string())
print('\npooled over all 8 sym/tf cells:')
P = F.groupby(['cand', 'R']).apply(lambda x: pd.Series({'trades': int(x.n.sum()), 'win%': np.average(x.win, weights=x.n),
     'expR': np.average(x.exp, weights=x.n), 'cells+': int((x.exp > 0).sum()), 'exp_tr': np.average(x.exp_tr.fillna(0), weights=x.n), 'exp_te': np.average(x.exp_te.fillna(0), weights=x.n)}))
print(P.round(3).to_string())
