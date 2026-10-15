import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rbs import prepared, simulate, atr
from fams import fam_breakout
START = pd.Timestamp('2026-04-03', tz='UTC')

def ctx(df):
    et = df.datetime.dt.tz_convert('America/New_York'); m = (et.dt.hour * 60 + et.dt.minute).values
    day = et.dt.date.values
    rth = (m >= 570) & (m < 960)
    return et, m, day, rth

def opening_range(df1_sym, minutes=5):
    """RTH opening range (09:30 + `minutes`) per ET date from 1-minute bars."""
    et = df1_sym.index.tz_convert('America/New_York')
    m = et.hour * 60 + et.minute
    sel = (m >= 570) & (m < 570 + minutes)
    g = df1_sym[sel].groupby(et[sel].date)
    return g.high.max().to_dict(), g.low.min().to_dict()

from rbs import load1
OR = {s: opening_range(load1(s)) for s in ('NQ', 'ES')}

def variant(df, sym, N=20, stopN=10, strong=True, or_filter=False, accel=0, skip_open=0, cooldown=0):
    et, m, day, rth = ctx(df)
    sig = fam_breakout(df, N=N, stopN=stopN, strong=strong)
    orh, orl = OR[sym]
    d = df.tj_diff.values; c = df.close.values
    out = []; last = {1: -10**9, -1: -10**9}
    for i, s, sw in sig:
        if df.datetime.iloc[i] < START or not rth[i] or m[i] < 570 + skip_open: continue
        if or_filter:
            hi, lo = orh.get(day[i]), orl.get(day[i])
            if hi is None or m[i] < 575: continue
            if s == 1 and not c[i] > hi: continue
            if s == -1 and not c[i] < lo: continue
        if accel and not ((d[i] - d[i - accel]) * s > 0): continue
        if i - last[s] <= cooldown: continue
        last[s] = i
        out.append((i, s, sw))
    return out

if __name__ == '__main__':
    V = {
     'F0 基準（突破 N20 + 強趨勢 + 盤中）':  dict(),
     'F1 + 開盤區間方向（站上ORH才多）':      dict(or_filter=True),
     'F2 + 趨勢加速（差值擴大）':             dict(accel=5),
     'F3 + 開盤前15分鐘不做':               dict(skip_open=15),
     'F4a 停損用 5 根':                    dict(stopN=5),
     'F4b 停損用 20 根':                   dict(stopN=20),
     'F5a 突破 N10':                      dict(N=10),
     'F5b 突破 N30':                      dict(N=30),
     'F5c 突破 N40':                      dict(N=40),
     'F7 同向冷卻 10 根':                  dict(cooldown=10),
     'F1+F2':                            dict(or_filter=True, accel=5),
     'F1+F3':                            dict(or_filter=True, skip_open=15),
    }
    EX = {'2R': dict(R=2.0), '1.5R': dict(R=1.5), '2R+趨勢出場': dict(R=2.0, trend_exit=True)}
    rows = []
    for sym in ('NQ', 'ES'):
        for tf in (1, 2, 3, 5):
            df = prepared(sym, tf)
            mon = df.datetime.dt.tz_convert('America/New_York').dt.month.values
            for vn, kw in V.items():
                sig = variant(df, sym, **kw)
                for en, ekw in EX.items():
                    t = simulate(df, sig, sym, **ekw)
                    if not len(t): continue
                    t['mon'] = mon[t.i.values]
                    for mo, g in t.groupby('mon'):
                        if mo == 9: continue
                        rows.append(dict(var=vn, exit=en, sym=sym, tf=tf, mon=mo, n=len(g), exp=g.R.mean(), win=100 * (g.R > 0).mean()))
    M = pd.DataFrame(rows); M.to_csv('round3.csv', index=False)
    pd.set_option('display.width', 250)
    S = M.groupby(['var', 'exit']).apply(lambda x: pd.Series({
        'cells+': f"{int((x.exp > 0).sum())}/{len(x)}", 'pooled exp': np.average(x.exp, weights=x.n),
        'July': np.average(x[x.mon == 7].exp, weights=x[x.mon == 7].n) if (x.mon == 7).any() else np.nan,
        'win%': np.average(x.win, weights=x.n), 'trades': int(x.n.sum())})).reset_index()
    print(S.sort_values('pooled exp', ascending=False).round(3).to_string(index=False))
