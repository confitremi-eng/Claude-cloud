"""Best 「階段 / EMA」 for the gamma flip setup on NQ RTH (the QQQ substitute), ZeroGEX months.

  cd indicators/backtest
  python3 -I rbs/gex_params.py

Setup = v3's GEX setup: original signal (stage, 0, EMA, 1) on NQ 1-minute cash-session bars, Trend Judge on the
signal's side (threshold 20 NQ points), QQQ below its gamma flip for buys / above for sells (ZeroGEX, the minute
before the signal closes). Signal close entry, two-bar stop, 60-bar exit or the session end, 1 point cost.
Prints a stage x EMA grid (signals, 1R win %, 3R net R per trade, one at a time 3R total), then the details of a
few settings, including Remi's usual (35, 0, 13, 1) and v3's default (30, 0, 8, 1). 前 / 後 = the two halves.
Small sample (2026-07 .. 10, about 3 months): read the grid for a plateau, not the single best cell.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import gex_trend as gt

STAGES = (15, 20, 25, 30, 35, 40, 50)
EMAS = (5, 8, 13, 21)


def setup_rows(df, H, stage, ema, start, end):
    s = mm.trend_signals(df, H, 1, stage, ema)
    s = s[(s.date >= start) & (s.date <= end)].copy()
    s = pd.concat([s, gt.feats(df, s)], axis=1); s = s[s.QQQ_flip.notna()]
    return s[(np.sign(s.dir) * s.side > 0) & (s.flip_d < 0)]


def seq_stats(y, R, cost):
    t = ss.seq(y.sort_values('i'), R)
    if len(t) == 0: return 0, 0.0, 0.0
    n = t[f'r{R:g}'].values - cost / t.risk.values; eq = np.cumsum(n)
    return len(t), n.sum(), float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))


def main():
    cost = 1.0
    one = mm.load_market('qqq', []); tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, 20.0, 40.0)
    start, end = '2026-06-29', '2026-10-14'
    res = {}
    for st in STAGES:
        for em in EMAS:
            res[(st, em)] = setup_rows(df, H, st, em, start, end)
    d = sorted(res[(30, 8)].date.unique()); split = d[len(d) // 2]
    print(f'NQ RTH 1 分 K，gamma flip setup（Trend Judge 順勢 + 朝 QQQ flip 走），{start} .. {end}，每筆扣 1 點')
    for title, fn in (('筆數', lambda y: f'{len(y):6d}'),
                      ('1R 勝率', lambda y: f'{100 * (y.r1 > 0).mean():5.1f}%' if len(y) else '     -'),
                      ('2R 每筆（扣成本）', lambda y: f'{(y.r2 - cost / y.risk).mean():+6.2f}' if len(y) else '     -'),
                      ('3R 每筆（扣成本）', lambda y: f'{(y.r3 - cost / y.risk).mean():+6.2f}' if len(y) else '     -'),
                      ('一次一筆 3R 合計', lambda y: f'{seq_stats(y, 3.0, cost)[1]:+6.1f}'),
                      ('一次一筆 3R 回撤', lambda y: f'{seq_stats(y, 3.0, cost)[2]:6.1f}')):
        print(f'\n## {title}（列：階段，欄：EMA）')
        print('        ' + ''.join(f'  EMA {e:<3}' for e in EMAS))
        for st in STAGES:
            print(f'   {st:>3}  ' + ''.join(f'  {fn(res[(st, e)]):>7}' for e in EMAS))
    print('\n## 細看（各自獨立；一次一筆 1R / 2R / 3R）')
    print(f'   {"":<16}   筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    for st, em in ((35, 13), (30, 8), (35, 8), (30, 13), (25, 8), (40, 8), (40, 13), (20, 8)):
        y = res[(st, em)]
        print(f'   {f"({st}, 0, {em}, 1)":<16} ' + mm.row_ind(y, cost, split))
        parts = []
        for R in (1.0, 2.0, 3.0):
            k, tot, dd = seq_stats(y, R, cost)
            parts.append(f'{R:g}R {k} 筆 {tot:+.1f}R（回撤 {dd:.1f}）')
        print(f'   {"":<16}   一次一筆：' + '  '.join(parts))


if __name__ == '__main__':
    main()
