"""Trend Judge threshold sweep for the Remi Superb filtered alerts on any Databento 1-minute file (NQ, ES).

  cd indicators/backtest
  python3 rbs/superb_sweep.py DATA.csv 成本 門檻,門檻,... [週期]
  e.g. python3 rbs/superb_sweep.py data/ES_1m_databento.csv 0.5 0,1,2,3,4,5,6,8
       python3 rbs/superb_sweep.py data/NQ_1m_databento.csv 1 5,10,15,20

Filter = Remi Superb's defaults: 有趨勢 (Trend Judge spread > 門檻 in the trade's direction), last complete
1-hour close on the trade's side of its EMA20, stop >= 1 ATR, data / open / close / Globex windows avoided
(Asia kept), close - 15-second EMA1130 <= 3 ATR. Also shown without the distance filter. One position at a
time, the given cost per trade (points), 前 / 後 = the two halves of the file by date.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp


def run(sub, R):
    t = ss.seq(sub, R)
    r = t[f'r{R:g}'].values; net = r - ss.COST / t.risk.values; a = t.date.values < ss.SPLIT
    L, S = t.side.values == 1, t.side.values == -1
    m = lambda v: v.mean() if len(v) else np.nan
    return (f'{len(t):5d} 筆  勝率 {100 * m(r > 0):4.1f}%  每筆 {m(net):+.3f}R（前 {m(net[a]):+.3f} 後 {m(net[~a]):+.3f}）'
            f'  合計 {net.sum():+6.1f}R | 多 {L.sum():4d} {100 * m(r[L] > 0):4.1f}% {m(net[L]):+.3f}'
            f'  空 {S.sum():4d} {100 * m(r[S] > 0):4.1f}% {m(net[S]):+.3f}')


def main():
    path, cost = sys.argv[1], float(sys.argv[2])
    ths = [float(v) for v in sys.argv[3].split(',')]
    tf = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    ss.COST = cost
    rbs.DATA['NQ'] = path                      # the research code reads 'NQ'
    tag = os.path.splitext(os.path.basename(path))[0]
    tw.TF = tf
    tw.CACHE = os.path.join(ss.DATA_DIR, f'{tag}_th_sweep_{tf}m.pkl') if 'NQ_1m_databento' not in tag or tf != 2 \
        else os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl')
    s = tw.build()
    s = pd.concat([s, mp.features(s, rbs.prepared('NQ', tf))], axis=1)
    d = sorted(s.date.unique()); ss.SPLIT = d[len(d) // 2]
    print(f'{tag}：{d[0]} .. {d[-1]}，{tf} 分 K，成本 {cost:g} 點，前 / 後 分界 {ss.SPLIT}')
    print('spread 分布（訊號方向，點）：', ' '.join(f'{q:.0%}={v:.2f}' for q, v in s.spread.quantile([.1, .25, .5, .75, .9]).items()))
    base = (s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s)
    for fname, fm in (('距離 ≤ 3 ATR（Remi Superb 預設）', s.tjSlow < 3), ('不加距離', s.side != 0)):
        for R in (1.0, 2.0, 3.0):
            print(f'\n  ## {fname}，{R:g}R')
            for th in ths:
                print(f'   門檻 {th:<5g} ' + run(s[base & fm & (s.spread > th)].sort_values('i'), R))
            print('   不看 TJ    ' + run(s[base & fm].sort_values('i'), R))


if __name__ == '__main__':
    main()
