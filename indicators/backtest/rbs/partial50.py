"""Two contracts, take one off at +50 points (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/partial50.py

v3 as now (2m trend 0-400, 5m 0-180, stop >= 0.95 ATR, slow line <= 3 ATR, FOMC days off, junk time off, one at a time,
trend + MIX; the 2m re-entry rule is left out). Two contracts per trade:
  v3        both contracts use v3's exits (stop, 3R / 2R target, 60 bars, halt)
  P50       contract 1 takes profit at +P points (or at the v3 target if that is closer); contract 2 keeps v3's exits
  P50 + BE  as P50, and once contract 1 is out, contract 2's stop moves to the entry (from the next bar)
Within a bar the stop is checked before any target. Points per trade for both contracts together, 1 point cost per contract.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def sim(C, trend, mix, R, P, be):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0
    def close_all(px):
        nonlocal pos
        p1 = got1 if got1 is not None else (px - ve) * pos
        out.append((d0, p1 + (px - ve) * pos - 2 * oc.COST)); pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            hp = got1 is None and P is not None and ((h[j] >= vp) if pos == 1 else (l[j] <= vp))
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                if not hs and hp: got1 = (vp - ve) * pos
                close_all(px)
            elif hp:
                got1 = (vp - ve) * pos
                if be: vs = ve
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, d0, got1 = k, px, st, px + R * (px - st), j, C.date[j], None
            vp = ve + k * min(P, abs(vt - ve)) if P else None
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                close_all(vs)
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vt, vb, d0, got1 = k, c[j], st, c[j] + R * (c[j] - st), j, C.date[j], None
            vp = ve + k * min(P, abs(vt - ve)) if P else None
    return pd.DataFrame(out, columns=['date', 'pts'])


def report(lab, t):
    yrs = [t[(t.date >= a) & (t.date <= b)].pts.sum() for nm, a, b in oc.YEARS]
    y = t[t.date > oc.YEARS[3][2]]; r = t[t.date >= '2026-07-19']
    eq = np.cumsum(y.pts.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
    mo = y.groupby(y.date.str[:7]).pts.sum()
    print(f'   {lab:<22} 每年點數（2 口）' + ' '.join(f'{v:+7.0f}' for v in yrs) + f'  | v3 那年 {len(y)} 筆 賺錢 {100 * (y.pts > 0).mean():.0f}% 每筆 {y.pts.mean():+.1f} 點 回撤 {dd:.0f} 點 賺錢月 {(mo > 0).sum()}/{len(mo)}；最近 3 個月 {r.pts.sum():+.0f} 點')


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
        print(f'\nNQ {tf}m（{R:g}R；每年點數：Y1 Y2 Y3 Y4 IS）')
        report('v3（兩口都同出場）', sim(C, T, mix, R, None, False))
        for P in (30, 50, 70):
            report(f'一口 +{P} 點先出', sim(C, T, mix, R, P, False))
            report(f'一口 +{P} 先出、另一口保本', sim(C, T, mix, R, P, True))


if __name__ == '__main__':
    main()
