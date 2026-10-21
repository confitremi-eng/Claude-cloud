"""Distance filter: from the 15 s slow line (v3) or from the 5 s fast line? (NQ 2m / 5m, five years)

  cd indicators/backtest
  python3 -I rbs/fast_dist.py

Remi (2026-10-21): a buy was blocked for being 4 ATR from the slow line, but the real problem is being far from the fast
line. v3 as now (2m trend 0-400, 5m 0-180, stop >= 0.95 ATR, FOMC days off, junk time off, one at a time, MIX unchanged)
with the distance rule swapped. Distance = (close - EMA1130) on the trade's side / ATR14 of the signal bar.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import flip_wait as fw


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        _, atr = ss.bar_context(df, tf)
        emaF = M.tdm['emaF'].reindex(pd.DatetimeIndex(df.last_min)).values
        s['fast'] = (df.close.values[s.i] - emaF[s.i]) * s.side / atr[s.i]
        base = (s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
        print(f'\nNQ {tf}m（{R:g}R；每年 R：Y1 Y2 Y3 Y4 IS）')
        rules = [('離慢線 ≤ 3 ATR（v3）', s.slow < 3), ('不限距離', s.slow < 99), ('離慢線 ≤ 4 ATR', s.slow < 4), ('離慢線 ≤ 5 ATR', s.slow < 5)]
        rules += [(f'離快線 ≤ {x:g} ATR（不看慢線）', s.fast < x) for x in (1.0, 1.5, 2.0, 2.5, 3.0)]
        rules += [(f'離慢線 ≤ 5 且離快線 ≤ {x:g}', (s.slow < 5) & (s.fast < x)) for x in (1.5, 2.0)]
        for lab, cond in rules:
            T = s[base & cond]
            t = oc.sim(C, T, mix, R, R)
            oc.one_line(f'{lab}（{len(T)}）', t)
            y = oc.year_stats(t[t.date > oc.YEARS[3][2]]); r = t[t.date >= '2026-07-19']
            print(f'      v3 那年 {y["n"]} 筆 勝 {y["win"]:.0f}% 每筆 {y["per"]:+.3f} 合計 {y["tot"]:+.0f} 回撤 {y["dd"]:.0f} 月 {y["months"]}；最近 3 個月 {r.net.sum():+.1f}R')
        # signals by fast-line distance, each on its own (v3 year)
        B = s[base].copy(); B['net'] = fw.each(C, B, R); B = B[B.date > oc.YEARS[3][2]]
        print('   v3 那年每個趨勢訊號單獨進場，依離快線 / 慢線的距離（ATR）：')
        for col, lab in (('fast', '快線'), ('slow', '慢線')):
            bins = [-99, 0, 1, 1.5, 2, 2.5, 3, 4, 99]
            g = B.groupby(pd.cut(B[col], bins), observed=True).net.agg(['count', 'mean', lambda v: (v > 0).mean()])
            print(f'      {lab}：' + '  '.join(f'{iv.left:g}~{iv.right:g} {int(r["count"])}筆 {r["mean"]:+.2f}R 勝{100 * r["<lambda_0>"]:.0f}%' for iv, r in g.iterrows()))


if __name__ == '__main__':
    main()
