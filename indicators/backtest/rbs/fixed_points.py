"""v3 with a fixed 60-point stop and a fixed 50- or 100-point target (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/fixed_points.py

Same v3 signals as now (2m trend 0-400, 5m 0-180, stop >= 0.95 ATR on the original two-bar stop, slow line <= 3 ATR,
FOMC days off, junk time off, one at a time). Only the exits change: stop 60 points from the entry, target 50 or 100
points (trend only, or trend + MIX). Results in points (1 point cost per trade) and in units of 60 points, against v3's
own exits converted to points.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import stop_target as stt


def sim_mixed(C, trend, mix, sp, tp, R_v3, mix_fixed=False):
    """sp None = v3 exits; otherwise trend (and MIX when mix_fixed) use stop sp / target tp points."""
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                out.append((d0, (px - ve) * pos - oc.COST)); pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vt, vb, d0 = k, px, st, px + R_v3 * (px - st), j, C.date[j]
            if sp is not None and mix_fixed: vs = px - k * sp; vt = px + k * tp
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                out.append((d0, (vs - ve) * pos - oc.COST)); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]
            pos, ve, vb, d0 = k, c[j], j, C.date[j]
            if sp is None:
                vs = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j]); vt = ve + R_v3 * (ve - vs)
            else:
                vs = ve - k * sp; vt = ve + k * tp
    return pd.DataFrame(out, columns=['date', 'pts'])


def report(lab, t):
    yrs = [t[(t.date >= a) & (t.date <= b)].pts.sum() for nm, a, b in oc.YEARS]
    y = t[t.date > oc.YEARS[3][2]]; r = t[t.date >= '2026-07-19']
    eq = np.cumsum(y.pts.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0
    print(f'   {lab:<30} 每年點數 ' + ' '.join(f'{v:+7.0f}' for v in yrs) + f'  | v3 那年 {len(y)} 筆 勝 {100 * (y.pts > 0).mean():.0f}% 每筆 {y.pts.mean():+.1f} 點 回撤 {dd:.0f} 點 = {dd / 60:.1f} 個 60 點；最近 3 個月 {r.pts.sum():+.0f} 點')


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
        print(f'\nNQ {tf}m（每年點數：Y1 Y2 Y3 Y4 IS）')
        report(f'v3 現在（兩根 K 停損、{R:g}R）', sim_mixed(C, T, mix, None, None, R))
        for tp in (50, 100):
            report(f'趨勢 停損 60 / 目標 {tp}，MIX 不變', sim_mixed(C, T, mix, 60, tp, R))
            report(f'趨勢和 MIX 都 停 60 / 標 {tp}', sim_mixed(C, T, mix, 60, tp, R, True))
        print('      v3 那年原本停損的距離：中位數 %.0f 點、平均 %.0f 點' % (T[T.date > oc.YEARS[3][2]].risk.median(), T[T.date > oc.YEARS[3][2]].risk.mean()))


if __name__ == '__main__':
    main()
