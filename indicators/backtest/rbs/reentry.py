"""Re-entry after a stop-out: if the trend is unchanged and price closes back past the entry within N bars, go again
(NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/reentry.py

v3 as now (2m trend 0-400, 5m 0-180, stop >= 0.95 ATR, slow line <= 3 ATR, FOMC days off, junk time off, one at a time,
trend + MIX). When a trade (trend or MIX) is stopped out, it may be re-entered once: within N bars of the stop, on a bar
whose close is back beyond the original entry (buy: above, sell: below) while Trend Judge is still on the trade's side
(UP / 強UP for a buy), not in an event / junk window, not on a FOMC day, not after the Friday cut-off. Entry at that
close. Stop: 'two-bar' = extreme of that bar and the one before (skip if < 0.95 ATR), or 'original' = the stopped
trade's stop. Target = v3's R multiple of the new risk. A re-entry that is stopped out is not re-entered again.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def sim(C, trend, mix, R, N, mode, evt, tjs, atr):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values; fomc = np.isin(np.asarray(C.date), list(ss.FOMC))
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0; re = None          # re = (side, entry, stop, until_bar)
    for j in range(len(c)):
        if pos != 0 and j > vb:
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                risk = abs(ve - vs0); out.append((d0, (px - ve) * pos / risk - oc.COST / risk, kind))
                if hs and N and kind != 're': re = (pos, ve, vs0, j + N)
                else: re = None
                pos = 0
        if holeb[j]: re = None
        if not trad[j] or C.halt[j] or C.late[j]: continue
        if pos == 0 and re is not None:
            k, e0, s0, until = re
            if j > until or tjs[j] == -k: re = None
            elif (c[j] - e0) * k > 0 and tjs[j] == k and not evt[j] and not fomc[j]:
                st = (min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])) if mode == 'two-bar' else s0
                risk = (c[j] - st) * k
                if risk > 0 and (mode != 'two-bar' or risk >= 0.95 * atr[j - 1]):
                    pos, ve, vs, vs0, vt, vb, d0, kind = k, c[j], st, st, c[j] + R * (c[j] - st), j, C.date[j], 're'
                re = None
                if pos: continue
        if pos == 0 and j in mx:
            k, px, st = mx[j]
            pos, ve, vs, vs0, vt, vb, d0, kind = k, px, st, st, px + R * (px - st), j, C.date[j], 'MIX'; re = None
            if (pos == 1 and l[j] <= vs) or (pos == -1 and h[j] >= vs):
                out.append((d0, -1.0 - oc.COST / abs(px - st), kind)); pos = 0
                if N: re = (k, px, st, j + N)
        if pos == 0 and j in tr:
            k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j])
            pos, ve, vs, vs0, vt, vb, d0, kind = k, c[j], st, st, c[j] + R * (c[j] - st), j, C.date[j], '趨勢'; re = None
    t = pd.DataFrame(out, columns=['date', 'net', 'kind']); t['R'] = t.net
    return t


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); wk = np.asarray(ny.weekday < 5)
        junk = (m >= 720) & (m <= 785)
        isf = np.isin(np.asarray(C.date), list(ss.FOMC))
        evt = (wk & (((m >= 508) & (m < 540)) | ((m >= 598) & (m < 615)))) | (isf & (m >= 838) & (m < 900)) | ((m >= 570) & (m < 600)) | \
              ((m >= 945) & (m < 975)) | ((m >= 1005) & (m < 1020)) | ((m >= 1080) & (m < 1110)) | junk
        tjs = np.sign(df.tj_dir.values).astype(int)
        _, atr = ss.bar_context(df, tf)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
        print(f'\nNQ {tf}m（{R:g}R；每年 R：Y1 Y2 Y3 Y4 IS）')
        for N, mode in ((0, '-'), (5, 'two-bar'), (10, 'two-bar'), (20, 'two-bar'), (10, 'original'), (20, 'original')):
            t = sim(C, T, mix, R, N, mode, evt, tjs, atr)
            lab = '不再進場（v3）' if N == 0 else f'{N} 根內收回，停損{"兩根 K" if mode == "two-bar" else "用原停損"}'
            oc.one_line(lab, t)
            y = t[t.date > oc.YEARS[3][2]]; ys = oc.year_stats(y); r = t[t.date >= '2026-07-19']; rr = y[y.kind == 're']
            print(f'      v3 那年 {ys["n"]} 筆 每筆 {ys["per"]:+.3f} 合計 {ys["tot"]:+.0f} 回撤 {ys["dd"]:.0f} 月 {ys["months"]}；最近 3 個月 {r.net.sum():+.1f}R'
                  + (f'；再進場 {len(rr)} 筆 勝 {100 * (rr.net > 0).mean():.0f}% 每筆 {rr.net.mean():+.2f}R' if len(rr) else ''))


if __name__ == '__main__':
    main()
