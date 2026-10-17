"""Win-rate matrix of the Remi Superb filtered alerts: timeframe x target, with and without the EMA1130 distance.

  cd indicators/backtest
  python3 rbs/superb_matrix.py DATA.csv 門檻 [成本] [週期,週期,...]
  e.g. python3 rbs/superb_matrix.py data/NQ_1m_databento.csv 15 1 1,2,3,5
       python3 rbs/superb_matrix.py data/ES_1m_databento.csv 4 0.5 1,2,3

Filter = Remi Superb's defaults: 有趨勢 (Trend Judge spread > 門檻), 1-hour EMA20 on the trade's side,
stop >= 1 ATR, data / open / close / Globex windows avoided (Asia kept), and the new option
close - 15-second EMA1130 <= 3 ATR in the trade's direction. One position at a time, the given cost
per trade (points), 前 / 後 = before / after 2026-06-01 (NQ year) or the two halves of the file.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw
import ma_position as mp

TARGETS = (1.0, 1.5, 2.0, 3.0)


def main():
    path, th = sys.argv[1], float(sys.argv[2])
    ss.COST = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    tfs = [int(v) for v in sys.argv[4].split(',')] if len(sys.argv) > 4 else [1, 2, 3, 5]
    rbs.DATA['NQ'] = path
    tag = os.path.splitext(os.path.basename(path))[0]
    rows = []
    for tf in tfs:
        rbs._cache.clear()
        tw.TF = tf
        tw.CACHE = os.path.join(ss.DATA_DIR, f'{tag}_th_sweep_{tf}m.pkl') if 'NQ_1m_databento' not in tag or tf != 2 \
            else os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl')
        s = tw.build()
        df = rbs.prepared('NQ', tf)
        s = pd.concat([s, mp.features(s, df)], axis=1)
        if tf == tfs[0]:
            d = sorted(s.date.unique())
            if d[0] >= '2026-06-01' or d[-1] < '2026-06-01':
                ss.SPLIT = d[len(d) // 2]
            print(f'資料 {d[0]} .. {d[-1]}，門檻 {th:g}，成本 {ss.COST:g} 點，前 / 後 分界 {ss.SPLIT}')
        base = (s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.spread > th)
        for fname, m in (('不加距離', base), ('距離 ≤ 3 ATR', base & (s.tjSlow < 3))):
            b = s[m].sort_values('i')
            for R in TARGETS:
                t = ss.seq(b, R)
                r = t[f'r{R:g}'].values; net = r - ss.COST / t.risk.values; a = t.date.values < ss.SPLIT
                L, S = t.side.values == 1, t.side.values == -1
                rows.append(dict(tf=f'{tf}m', f=fname, R=f'{R:g}R', n=len(t), win=100 * (r > 0).mean(), net=net.mean(),
                                 A=net[a].mean(), B=net[~a].mean(), tot=net.sum(),
                                 wl=100 * (r[L] > 0).mean(), nl=net[L].mean(), ws=100 * (r[S] > 0).mean(), ns=net[S].mean()))
    G = pd.DataFrame(rows)
    for fname in ('距離 ≤ 3 ATR', '不加距離'):
        g = G[G.f == fname]
        print(f'\n######## {fname}')
        print('  勝率（%）'); print(g.pivot(index='tf', columns='R', values='win').round(1).to_string())
        print('  每筆淨利（R）'); print(g.pivot(index='tf', columns='R', values='net').round(3).to_string())
        for _, x in g.iterrows():
            print(f'  {x.tf} {x.R:<4} {x.n:5d} 筆  勝率 {x.win:4.1f}%  每筆 {x.net:+.3f}R（前 {x.A:+.3f} 後 {x.B:+.3f}）  合計 {x.tot:+6.1f}R'
                  f'  | 多 {x.wl:4.1f}% {x.nl:+.3f}  空 {x.ws:4.1f}% {x.ns:+.3f}')


if __name__ == '__main__':
    main()
