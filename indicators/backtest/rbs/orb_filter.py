"""Opening range direction (Remi's ORB indicator, LuxAlgo 'Opening Range with Breakouts & Targets' idea) as a filter for v3.

  cd indicators/backtest
  python3 -I rbs/orb_filter.py

Opening range = the first 30 minutes of a session: 'Globex' 18:00-18:30 New York (the chart's session start on NQ1!)
or 'cash' 09:30-10:00. ORH / ORL / ORM (mid). Day bias = today's ORM vs the previous session's ORM (up / down).
A range applies from its end until the next range of the same kind starts. Filters on v3 signals (trend and MIX):
  bias      : trade only in the day-bias direction
  outside   : buy only above ORH, sell only below ORL
  mid       : buy above ORM, sell below ORM
  bias+mid
v3 as now (2m trend 0-400, 5m 0-180 + daily SMA5 / 0.25%, stop >= 0.95 ATR, FOMC, junk time, New York 15:45-18:30 off;
one at a time). Per year: win rate / R.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5


def ranges(one, start):
    """Per 1-minute bar: (orh, orl, orm, bias) of the latest completed range that started at `start` (minutes NY)."""
    ix = one.index if one.index.tz is not None else one.index.tz_localize('UTC')
    ny = ix.tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
    h, l = one.high.values, one.low.values
    n = len(m); OH = np.full(n, np.nan); OL = np.full(n, np.nan); OM = np.full(n, np.nan); B = np.zeros(n)
    cur = None; building = False; prev_m = np.nan; done = (np.nan, np.nan, np.nan, 0)
    for j in range(n):
        if m[j] == start:
            building = True; cur = [h[j], l[j]]
        elif building and start <= m[j] < start + 30:
            cur[0] = max(cur[0], h[j]); cur[1] = min(cur[1], l[j])
        elif building:
            building = False
            om = (cur[0] + cur[1]) / 2
            bias = 0 if np.isnan(prev_m) else (1 if om > prev_m else -1 if om < prev_m else 0)
            prev_m = om; done = (cur[0], cur[1], om, bias)
        if not building:
            OH[j], OL[j], OM[j], B[j] = done
    return pd.DataFrame({'orh': OH, 'orl': OL, 'orm': OM, 'bias': B}, index=one.index)


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    R_ = {'Globex 18:00': ranges(one, 1080), '美股 09:30': ranges(one, 570)}
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
        lm = pd.DatetimeIndex(df.last_min)
        print(f'\nNQ {tf}m（{R:g}R）每年：勝率 / 合計 R')
        print(f'   {"":<26}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
        def row(lab, TT, MM):
            t = oc.sim(C, TT, MM, R, R)
            print(f'   {lab:<26}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS)) + f'   {len(t) / 5:.0f} 筆 / 年')
        row('v3 現在', T, mix)
        for rn, RG in R_.items():
            g = RG.reindex(lm); oh, ol, om, bi = g.orh.values, g.orl.values, g.orm.values, g.bias.values
            px_t = c
            rules = {
                '方向（今天中線 vs 昨天）': lambda j, k, px: bi[j] == k,
                '在區間外（買 > ORH）': lambda j, k, px: (px > oh[j]) if k == 1 else (px < ol[j]),
                '在中線同側': lambda j, k, px: (px - om[j]) * k > 0,
                '方向 + 中線同側': lambda j, k, px: bi[j] == k and (px - om[j]) * k > 0,
            }
            for lab, f in rules.items():
                keep = np.array([f(i, k, c[i]) for i, k in zip(T.i.values, T.side.values)])
                row(f'{rn}：{lab}', T[keep], [x for x in mix if f(x[0], x[1], x[2])])


if __name__ == '__main__':
    main()
