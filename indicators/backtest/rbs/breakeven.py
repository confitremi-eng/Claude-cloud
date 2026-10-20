"""Break-even stop for v3 (NQ 2m / 5m, five years): move the stop to the entry once the trade is up X R?

  cd indicators/backtest
  python3 -I rbs/breakeven.py

v3 as now (2m trend 0-400, 5m 0-180, stop >= 0.95 ATR, FOMC days off, junk time 12:00-13:05 off, one at a time,
trend + MIX). R is always the original stop distance. Once a bar's high (buy) / low (sell) reaches entry + X R, the
stop moves to entry + L R from the next bar on (L = 0: break-even, the 1 point cost still counts). Within a bar the
stop is checked before the target (conservative).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc

RULES = [(None, 0), (1.0, 0.0), (1.5, 0.0), (2.0, 0.0), (2.0, 1.0), (2.5, 1.0)]


def sim(C, trend, mix, R, trig, lock):
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
                out.append((d0, (px - ve) * pos / risk - oc.COST / risk, moved)); pos = 0
            elif trig is not None and not moved and ((h[j] - ve) * pos >= trig * risk if pos == 1 else (ve - l[j]) >= trig * risk):
                vs = ve + pos * lock * risk; moved = True
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vb, d0, moved = k, px, st, j, C.date[j], False; risk = abs(px - st); vt = px + R * (px - st)
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                out.append((d0, -1.0 - oc.COST / risk, False)); pos = 0
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vb, d0, moved = k, c[j], st, j, C.date[j], False; risk = abs(ve - st); vt = ve + R * (ve - st)
    t = pd.DataFrame(out, columns=['date', 'net', 'moved']); t['R'] = t.net
    return t


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3.0) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC)]
        T = T[~junk[T.i.values]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
        print(f'\nNQ {tf}m（{R:g}R；每年 R：Y1 Y2 Y3 Y4 IS）')
        for trig, lock in RULES:
            if trig is not None and trig >= R: continue
            t = sim(C, T, mix, R, trig, lock)
            lab = '不移動（v3）' if trig is None else (f'到 {trig:g}R 移到保本' if lock == 0 else f'到 {trig:g}R 鎖 {lock:g}R')
            oc.one_line(lab, t)
            y = oc.year_stats(t[t.date > oc.YEARS[3][2]]); r = t[t.date >= '2026-07-19']
            print(f'      v3 那年 {y["n"]} 筆 勝 {y["win"]:.0f}% 每筆 {y["per"]:+.3f} 合計 {y["tot"]:+.0f} 回撤 {y["dd"]:.0f} 月 {y["months"]}；最近 3 個月 {r.net.sum():+.1f}R')


if __name__ == '__main__':
    main()
