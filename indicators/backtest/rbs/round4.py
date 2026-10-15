import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rbs import prepared, simulate, ema
from round3 import variant
def adx(df, n=14):
    h, l, c = df.high.values, df.low.values, df.close.values
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    r = lambda x: pd.Series(x).ewm(alpha=1 / n, adjust=False).mean().values
    pdi = 100 * r(pdm) / r(tr); mdi = 100 * r(mdm) / r(tr)
    return r(100 * np.abs(pdi - mdi) / np.where(pdi + mdi == 0, 1, pdi + mdi))
def er(df, n=20):
    c = df.close.values
    ch = np.abs(c - np.r_[np.full(n, np.nan), c[:-n]])
    vol = pd.Series(np.abs(np.diff(c, prepend=c[0]))).rolling(n).sum().values
    return ch / np.where(vol == 0, np.nan, vol)
if __name__ == '__main__':
    rows = []
    for sym in ('NQ', 'ES'):
        for tf in (1, 2, 3, 5):
            df = prepared(sym, tf)
            mon = df.datetime.dt.tz_convert('America/New_York').dt.month.values
            A = adx(df); E = er(df)
            tests = {}
            for N in (20, 30, 40, 50, 60):
                tests[f'N{N}'] = variant(df, sym, N=N)
            base = variant(df, sym, N=30)
            for th in (20, 25, 30):
                tests[f'N30 + ADX>{th}'] = [s for s in base if A[s[0]] > th]
            for th in (0.3, 0.4, 0.5):
                tests[f'N30 + ER20>{th}'] = [s for s in base if E[s[0]] > th]
            for vn, sig in tests.items():
                t = simulate(df, sig, sym, R=2.0)
                if not len(t): continue
                t['mon'] = mon[t.i.values]
                for mo, g in t.groupby('mon'):
                    if mo == 9: continue
                    rows.append(dict(var=vn, sym=sym, tf=tf, mon=mo, n=len(g), exp=g.R.mean(), win=100 * (g.R > 0).mean()))
    M = pd.DataFrame(rows); M.to_csv('round4.csv', index=False)
    pd.set_option('display.width', 250)
    S = M.groupby('var').apply(lambda x: pd.Series({
        'cells+': f"{int((x.exp > 0).sum())}/{len(x)}", 'pooled exp': np.average(x.exp, weights=x.n),
        'July': np.average(x[x.mon == 7].exp, weights=x[x.mon == 7].n),
        'ex-July': np.average(x[x.mon != 7].exp, weights=x[x.mon != 7].n),
        'win%': np.average(x.win, weights=x.n), 'trades': int(x.n.sum())})).reset_index()
    print(S.sort_values('pooled exp', ascending=False).round(3).to_string(index=False))
