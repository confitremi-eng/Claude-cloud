"""Filtered alerts, long and short separately, all hours (NQ 1 / 2 / 3 / 5 minutes).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/long_short.py [--rebuild] [--th 15,35]

--th: Trend Judge thresholds (一般,強勢). Default 20,40 (Remi's Buy/Sell); 15,35 is Remi Superb.

Filter = the filtered alerts with Trend Judge mode 「有趨勢（一般 + 強）」: Trend Judge UP / 強UP for a buy
(DOWN / 強Down for a sell), last complete 1-hour close on the same side of its EMA20, stop >= 1 ATR.
No time windows are avoided ("全時段"); a second table also avoids the data / open / close / Globex
windows (Remi Superb's default: avoid those, keep the Asia session).
Signals, exits and costs come from setup_study.py (user's stop, fixed R, 60-bar time exit, 1 point cost),
one position at a time across both sides, then split by side. Reuses setup_study's cache if it exists.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss

FILT = lambda x: (x.side * x.dir >= 1) & (x.side == x.h1) & (x.risk_atr >= 1.0)


def line(t, R):
    r = t[f'r{R:g}'].values; net = r - ss.COST / t.risk.values
    if len(t) == 0: return '    0 筆'
    return f'{len(t):5d} 筆  勝率 {100 * (r > 0).mean():4.1f}%  每筆淨 {net.mean():+.3f}R  合計 {net.sum():+7.1f}R'


def main():
    if '--th' in sys.argv:
        th = tuple(float(v) for v in sys.argv[sys.argv.index('--th') + 1].split(','))
        rbs.TH['NQ'] = th
        ss.CACHE = ss.CACHE.replace('.pkl', f'_th{th[0]:g}_{th[1]:g}.pkl')
    s = pd.read_pickle(ss.CACHE) if os.path.exists(ss.CACHE) and '--rebuild' not in sys.argv else ss.build()
    print(f'資料：{s.date.min()} .. {s.date.max()}  Trend Judge 門檻 {rbs.TH["NQ"][0]:g} / {rbs.TH["NQ"][1]:g}')
    for title, extra in (('全時段', lambda x: x.side != 0), ('避開數據、開收盤、Globex（亞洲盤照做）', lambda x: ~ss.EVT(x))):
        print(f'\n######## 過濾開啟（有趨勢 + 1h + 停損 >= 1 ATR），{title}，一次一筆，扣 1 點成本')
        for tf in (1, 2, 3, 5):
            x = s[s.tf == tf].sort_values('i')
            sub = x[FILT(x) & extra(x)]
            for R in (1.0, 2.0):
                t = ss.seq(sub, R)
                print(f'  {tf}m {R:g}R  做多 {line(t[t.side == 1], R)}   做空 {line(t[t.side == -1], R)}')


if __name__ == '__main__':
    main()
