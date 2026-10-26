"""Autotrade with NQ 2m + 5m (24-hour charts) and NQ RTH 1m (the QQQ setting on NQ prices) sharing one MNQ position.
The Databento year (2025-10 .. 2026-10).

  cd indicators/backtest
  python3 -I rbs/combo_rth1m.py

2m / 5m: v3 trend signals with today's filters (stop >= 0.95 ATR, slow line <= 3 ATR, trend 0-400 / 0-180 minutes,
events, FOMC, junk time ET 12:00-13:05, ET 15:15-18:30, Monday Taipei 06-15; the 5m daily-SMA5 filter is left out
here) + MIX (not ET 16-20, same time filters); 3R / 2R. RTH 1m: oos_check.nq_rth (35, 0, 8, 1), Trend Judge 20 / 40,
slow line <= 7 ATR, NQ 2m not opposite, 3R, flat at the 16:00 close. Each chart trades on its own; autotrade takes a
trade only when flat (first come owns the position; same-minute ties: 2m, 5m, 1m). 2 MNQ, 1 point cost.
Also: during the US cash session (ET 09:30-16:00) only RTH 1m, 2m / 5m only outside it.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import mix_opt as mo
import oos_check as oc
import combo_2m5m as cb


def offmask(df, tf):
    ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
    m = np.asarray(ny.hour * 60 + ny.minute); tp = ny.tz_convert('Asia/Taipei'); tm = np.asarray(tp.hour * 60 + tp.minute)
    return ((m >= 720) & (m <= 785)) | ((m >= 915) & (m < 1110)) | ((np.asarray(tp.weekday) == 0) & (tm >= 360) & (tm < 900))


def current_trend(C, H, tf, hi):
    df = C.df; s = mm.trend_signals(df, H, tf, 20, 8); off = offmask(df, tf)
    F = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > mo.TH) & (s.tm < hi)
          & ~s.date.isin(ss.FOMC) & ~off[s.i]]
    C.trend = {int(i): (int(k), (min(C.l[i - 1], C.l[i]) if k == 1 else max(C.h[i - 1], C.h[i])), '趨勢') for i, k in zip(F.i, F.side)}
    keep = ~off & ~pd.Series(C.date).isin(ss.FOMC).values
    orig = mo.breaks
    mo.breaks = lambda C_, bx: [x for x in orig(C_, bx) if keep[x[0]]]
    return orig


def rth_trades(one):
    df, t = oc.nq_rth(one, detail=True)
    step = pd.Timedelta(minutes=1)
    lm = pd.DatetimeIndex(df.last_min.values)
    et = lm[t.i.values] + step; xt = lm[np.minimum(t.x3.values.astype(int), len(df) - 1)] + step
    e = df.close.values[t.i.values]; side = t.side.values; R = t.r3.values; risk = t.risk.values
    out = pd.DataFrame({'kind': '趨勢', 'side': side, 'entry': e, 'exit': e + side * R * risk, 'risk': risk,
                        'et': et.values, 'xt': xt.values, 'date': t.date.values})
    out['tf'] = 1; out['R'] = R; out['net'] = R - oc.COST / risk; out['pts'] = R * risk - oc.COST
    return out


def combine3(frames):
    t = pd.concat([f.assign(pri=p) for p, f in enumerate(frames)]).sort_values(['et', 'pri'], kind='stable')
    keep, busy = [], np.datetime64('1970-01-01')
    for r in t.itertuples():
        ok = np.datetime64(r.et) >= busy
        keep.append(ok)
        if ok: busy = np.datetime64(r.xt)
    t = t.assign(taken=keep)
    return t[t.taken].drop(columns=['pri', 'taken']).reset_index(drop=True), t[~t.taken]


def main():
    one = mm.load_market('nq', []); one['bad'] = False
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    C2, C5 = mo.Ctx(2, one, tdm, H), mo.Ctx(5, one, tdm, H)
    o = current_trend(C2, H, 2, 400); t2 = cb.v3_trades(C2, 3.0, one); mo.breaks = o
    o = current_trend(C5, H, 5, 180); t5 = cb.v3_trades(C5, 2.0, one); mo.breaks = o
    t1 = rth_trades(one)
    for t in (t2, t5, t1):
        t['et'] = pd.to_datetime(t.et, utc=True); t['xt'] = pd.to_datetime(t.xt, utc=True)
    years, split = C2.years, C2.split
    print(f'NQ，MNQ 固定 2 口，每筆扣 1 點，{years:.2f} 年')
    for lab, t in (('只做 2m', t2), ('只做 5m', t5), ('只做 RTH 1m', t1)):
        print(f'  {lab:<24}' + cb.line(t, years, split))
    def outside_rth(t):
        ny = pd.DatetimeIndex(t.et).tz_convert('America/New_York'); m = ny.hour * 60 + ny.minute
        return t[~((ny.weekday < 5) & (m >= 570) & (m < 960))]
    t2o, t5o = outside_rth(t2), outside_rth(t5)
    for lab, fr in (('2m + 5m（現在）', [t2, t5]), ('2m + 5m + RTH 1m', [t2, t5, t1]), ('2m + RTH 1m', [t2, t1]),
                    ('盤中只做 RTH 1m（2m/5m 只做盤外）', [t2o, t5o, t1]), ('盤中只做 RTH 1m（2m 只做盤外，沒有 5m）', [t2o, t1])):
        both, lost = combine3(fr)
        print(f'  {lab:<34}' + cb.line(both, years, split))
        for tf in sorted(both.tf.unique()):
            x = both[both.tf == tf]; y = lost[lost.tf == tf]
            print(f'      {tf} 分：做了 {len(x) / years:.0f} 筆/年 {x.pts.sum() / years:+.0f} 點；被占住沒做 {len(y) / years:.0f} 筆/年（自己 {y.pts.sum() / years:+.0f} 點）')


if __name__ == '__main__':
    main()
