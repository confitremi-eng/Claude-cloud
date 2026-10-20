"""NQ MIX-box breakout on 5 (and 2) minutes over five years (2021-10 .. 2026-10), MIX only, one at a time.

  cd indicators/backtest
  python3 -I rbs/mix5_oos.py [5 | 2]          # default 5

Base = v3: Trend Judge MIX (+-10 points) for 60 minutes -> box, first break of 10% within 60 minutes, stop order at the
break, stop at the middle, no MIX 16-20 New York, no new trades from Taipei Saturday 02:00, 60-bar exit, 17:00 halt,
1 point cost. The grid (target 1-5R x box 60 / 90 / 120 minutes x stop at 0.5 / 0.75 / 1 of the box, and skipping
breaks in the first 10 minutes) is shown whole, per year, to see whether anything holds in every year -- not to pick
the best cell. Years and data as rbs/oos_check.py; Y1-Y4 are out of sample, IS is the year v3 was built on.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import mix_breakout as mb
import mix_opt as mo
import oos_check as oc


def run(tf):
    one = oc.load(); M = oc.Market(one); C = M.ctx(tf)
    empty = C.df.iloc[0:0].assign(i=[], side=[])
    print(f'NQ {tf} 分 K，只做 MIX 突破（一次一筆），每筆扣 1 點；每年 R：' + '  '.join(nm[:2] for nm, a, b in oc.YEARS))
    rows = []
    for box in (60, 90, 120):
        bx = mb.causal_boxes(C.B, C.bars(box), grace=max(0, round(4 / tf)))
        for sf in (0.5, 0.75, 1.0):
            for skip in (0, 10):
                cands = [x for x in mo.breaks(C, bx, valid_min=60, stop_f=sf, skip_min=skip) if x[4]['sess'] != '收盤後 16-20']
                for R in (1.0, 2.0, 3.0, 4.0, 5.0):
                    t = oc.sim(C, empty, cands, R, R)
                    yrs = [oc.year_stats(t[(t.date >= a) & (t.date <= b)]) for nm, a, b in oc.YEARS]
                    o = oc.year_stats(t[(t.date >= oc.YEARS[0][1]) & (t.date <= oc.YEARS[3][2])])
                    rows.append(dict(box=box, stop=sf, skip=skip, R=R, yrs=[y['tot'] for y in yrs], win=[y['win'] for y in yrs],
                                     oos=o['per'], n=o['n'], pos=sum(y['tot'] > 0 for y in yrs[:4])))
    base = [r for r in rows if r['box'] == 60 and r['stop'] == 0.5 and r['skip'] == 0]
    print('\n## v3 做法（區間 60 分、停損中線），換目標')
    print(f'   {"目標":<6} ' + '  '.join(f'{nm[:2]:>6}' for nm, a, b in oc.YEARS) + '   樣本外每筆  賺錢年  樣本外勝率（逐年）')
    for r in base:
        print(f'   {r["R"]:g}R     ' + '  '.join(f'{v:+6.0f}' for v in r['yrs']) + f'   {r["oos"]:+.3f}     {r["pos"]}/4   ' + ' '.join(f'{w:4.1f}%' for w in r['win'][:4]))
    print('\n## 全部組合（區間、停損、前 10 分作廢 × 目標），樣本外每筆 R / 賺錢年')
    print(f'   {"區間 停損 前10分":<16} ' + '  '.join(f'{R:g}R'.rjust(12) for R in (1, 2, 3, 4, 5)))
    for box in (60, 90, 120):
        for sf in (0.5, 0.75, 1.0):
            for skip in (0, 10):
                cells = [r for r in rows if r['box'] == box and r['stop'] == sf and r['skip'] == skip]
                print(f'   {box:>3} 分 {sf:<4g} {"作廢" if skip else "照做":<4}  ' + '  '.join(f'{r["oos"]:+.3f} {r["pos"]}/4'.rjust(12) for r in cells))
    good = [r for r in rows if r['pos'] >= 3 and r['oos'] > 0]
    print(f'\n共 {len(rows)} 組；樣本外合計賺錢而且 4 年至少 3 年賺的：{len(good)} 組')
    for r in sorted(good, key=lambda r: -r['oos'])[:10]:
        print(f'   區間 {r["box"]} 分、停損 {r["stop"]:g}、前 10 分{"作廢" if r["skip"] else "照做"}、{r["R"]:g}R：每年 ' + ' '.join(f'{v:+.0f}' for v in r['yrs']) + f'，樣本外每筆 {r["oos"]:+.3f}（{r["n"]} 筆）')


if __name__ == '__main__':
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
