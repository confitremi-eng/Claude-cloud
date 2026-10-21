"""After a pullback of X R, how do v3 trades end — and does cutting them there help? (NQ 2m / 5m, five years)

  cd indicators/backtest
  python3 -I rbs/early_cut.py

v3 as now (2m trend 0-400, 5m 0-180 + daily SMA5 / 0.25%, stop >= 0.95 ATR, FOMC, junk time, New York 15:45-18:30 off;
one at a time; trend + MIX). Part 1: of the trades that went X R against the entry, the share that still hit the
target / were stopped / timed out. Part 2: exit at -X R instead of the stop (target and everything else unchanged);
R is still the original stop distance. Per year: win rate / R.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5


def sim(C, trend, mix, R, cut):
    df = C.df; h, l, c = C.h, C.l, C.c
    holeb = np.r_[False, (df.datetime.diff() > pd.Timedelta(minutes=30)).values[1:]]
    trad = df.tradable.values
    tr = {int(i): int(k) for i, k in zip(trend.i, trend.side)}
    mx = {j: (k, px, st) for j, k, px, st, _ in mix}
    out = []; pos = 0
    for j in range(len(c)):
        if pos != 0 and j > vb:
            adv = (ve - l[j]) if pos == 1 else (h[j] - ve)
            mae = max(mae, adv / risk)
            hs = (l[j] <= vs) if pos == 1 else (h[j] >= vs)
            ht = (h[j] >= vt) if pos == 1 else (l[j] <= vt)
            if hs or ht or j - vb >= 60 or C.halt[j] or holeb[j]:
                px = vs if hs else vt if ht else (c[j - 1] if holeb[j] else c[j])
                why = '停損' if hs else '目標' if ht else '時間'
                out.append((d0, kind, (px - ve) * pos / risk - oc.COST / risk, mae, why)); pos = 0
        if not trad[j] or C.halt[j] or C.late[j]: continue
        for src in ('mix', 'tr'):
            if pos != 0: break
            if src == 'mix' and j in mx:
                k, px, st = mx[j]; e = px; kind = 'MIX'
            elif src == 'tr' and j in tr:
                k = tr[j]; st = min(l[j - 1], l[j]) if k == 1 else max(h[j - 1], h[j]); e = c[j]; kind = '趨勢'
            else:
                continue
            risk = abs(e - st)
            pos, ve, vb, d0, mae = k, e, j, C.date[j], 0.0
            vs = e - k * cut * risk if cut else st
            vt = e + k * R * risk
            if src == 'mix':
                adv0 = (e - l[j]) if k == 1 else (h[j] - e); mae = adv0 / risk
                if (k == 1 and l[j] <= vs) or (k == -1 and h[j] >= vs):
                    out.append((d0, kind, (vs - ve) * k / risk - oc.COST / risk, mae, '停損')); pos = 0
    return pd.DataFrame(out, columns=['date', 'kind', 'net', 'mae', 'why'])


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
        skip = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
        sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~skip[s.i]]
        if tf == 5: T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not skip[x[0]] and (tf != 5 or ((x[2] - sma[x[0]]) * x[1] > 0 and abs(x[2] - sma[x[0]]) / x[2] * 100 >= 0.25))]
        base = sim(C, T, mix, R, None)
        print(f'\nNQ {tf}m（{R:g}R）')
        for per, z in (('v3 那年', base[base.date > oc.YEARS[3][2]]), ('前 4 年', base[base.date <= oc.YEARS[3][2]])):
            for X in (0.25, 0.5, 0.75):
                g = z[z.mae >= X]
                print(f'   {per}：回檔到 {X:g}R 的單 {len(g)} 筆（全部 {len(z)} 筆的 {100 * len(g) / len(z):.0f}%）→ 到目標 {100 * (g.why == "目標").mean():.0f}%、停損 {100 * (g.why == "停損").mean():.0f}%、時間出場 {100 * (g.why == "時間").mean():.0f}%，每筆 {g.net.mean():+.2f}R')
        print(f'   {"":<22}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
        for cut in (None, 0.5, 0.75):
            t = base if cut is None else sim(C, T, mix, R, cut)
            lab = '停損不動（v3）' if cut is None else f'回檔 {cut:g}R 就出場'
            print(f'   {lab:<22}' + ''.join(f'{100 * (q.net > 0).mean():5.0f}% {q.net.sum():+5.0f}R' for q in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS)))


if __name__ == '__main__':
    main()
