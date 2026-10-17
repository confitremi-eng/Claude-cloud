"""Remi's Buy/Sell filtered alerts on ES (a Databento ES file built with build_databento.py).

  cd indicators/backtest
  python3 rbs/es_check.py data/ES_1m_databento.csv

Runs the NQ research code on ES: thresholds in ES points, 0.5 point cost per trade (rbs.COST['ES']).
Prints
  1. long / short per timeframe (1 / 2 / 3 / 5 minutes) for the Remi Superb thresholds 3 / 6 and the
     Remi's Buy/Sell thresholds 4 / 8 (有趨勢 + 1h + stop >= 1 ATR, all hours and avoiding event windows)
  2. a 2-minute 有趨勢 threshold sweep in ES points
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import long_short as ls

ES_COST = rbs.COST['ES']


def main():
    path = sys.argv[1]
    rbs.DATA['NQ'] = path                      # the research code reads 'NQ'; point it at the ES file
    ss.COST = ES_COST
    tag = os.path.splitext(os.path.basename(path))[0]
    for th in ((3.0, 6.0), (4.0, 8.0)):
        rbs.TH['NQ'] = th
        rbs._cache.clear()
        ss.CACHE = os.path.join(ss.DATA_DIR, f'{tag}_setup_th{th[0]:g}_{th[1]:g}.pkl')
        s = ss.build()
        print(f'\n==== ES {s.date.min()} .. {s.date.max()}，門檻 {th[0]:g} / {th[1]:g}，扣 {ES_COST:g} 點')
        for title, extra in (('全時段', lambda x: x.side != 0), ('避開事件時段', lambda x: ~ss.EVT(x))):
            print(f'  ## {title}')
            for tf in (1, 2, 3, 5):
                x = s[s.tf == tf].sort_values('i')
                sub = x[ls.FILT(x) & extra(x)]
                for R in (1.0, 2.0):
                    t = ss.seq(sub, R)
                    print(f'  {tf}m {R:g}R  做多 {ls.line(t[t.side == 1], R)}   做空 {ls.line(t[t.side == -1], R)}')

    rbs._cache.clear()
    tw.CACHE = os.path.join(ss.DATA_DIR, f'{tag}_th_sweep_2m.pkl')
    s = tw.build()
    base = (s.side == s.h1) & (s.risk_atr >= 1.0)
    print(f'\n==== ES 2 分 K 門檻掃描（有趨勢：spread > 門檻），扣 {ES_COST:g} 點')
    print('spread 分布（訊號方向，點）：', ' '.join(f'{q:.0%}={v:.1f}' for q, v in s.spread.quantile([.1, .25, .5, .75, .9]).items()))
    for hn, hm in (('全時段', s.side != 0), ('避開事件時段', ~ss.EVT(s))):
        for R in (1.0, 2.0):
            print(f'  {hn}，{R:g}R')
            for th in (0, 1, 2, 3, 4, 5, 6, 8, 10):
                print('   ' + tw.row(f'門檻 {th:g}', tw.run(s[base & hm & (s.spread > th)], R)))
            print('   ' + tw.row('不看 TJ', tw.run(s[base & hm], R)))


if __name__ == '__main__':
    main()
