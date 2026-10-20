"""One fixed Trend Judge threshold per year: which would have worked, and could it have been picked in advance?

  cd indicators/backtest
  python3 -I rbs/year_th.py [2 | 5]          # default both

v3 frozen except the threshold (一般 X points, 強 3.5 X; MIX boxes use the same X), NQ 2m (3R) and 5m (2R), years
October to October as rbs/oos_check.py. Prints the whole grid of yearly R (hindsight: the best cell of each year is
only known afterwards), then two ways that are known at the start of each year:
  前一年最好   use the threshold that did best the year before (walk-forward)
  依年初價格   10 points x real NQ price at the start of the year / the v3 year's average price, rounded to the grid
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import oos_check as oc

GRID = (4.0, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0, 20.0)


def run(one, M, tf, R):
    tab = {}
    for th in GRID:
        t = M.nq(tf, R, 0, 180, th=th)
        tab[th] = [oc.year_stats(t[(t.date >= a) & (t.date <= b)])['tot'] for nm, a, b in oc.YEARS]
        M._c.pop((tf, th), None)                                    # free the chart before the next threshold
    names = [nm[:2] for nm, a, b in oc.YEARS]
    print(f'\n## NQ {tf}m（趨勢 0–180 + MIX，{R:g}R），每年 R')
    print('   門檻   ' + '  '.join(f'{n:>7}' for n in names) + '   樣本外 4 年')
    for th in GRID:
        v = tab[th]
        print(f'   {th:4g}   ' + '  '.join(f'{x:+7.0f}' for x in v) + f'   {sum(v[:4]):+8.0f}')
    best = [max(GRID, key=lambda th: tab[th][k]) for k in range(len(names))]
    print('   事後最好的門檻：' + '  '.join(f'{n} {b:g} 點（{tab[b][k]:+.0f}R）' for k, (n, b) in enumerate(zip(names, best))))
    # walk-forward: year k uses the best threshold of year k-1
    wf = [None] + [best[k - 1] for k in range(1, len(names))]
    wf_r = [tab[wf[k]][k] for k in range(1, len(names))]
    print('   前一年最好：' + '  '.join(f'{names[k]} 用 {wf[k]:g} 點 → {tab[wf[k]][k]:+.0f}R' for k in range(1, len(names)))
          + f'；Y2–Y4 合計 {sum(wf_r[:3]):+.0f}R（固定 10 點 {sum(tab[10.0][1:4]):+.0f}R）')
    # price at the start of each year
    sc = oc.scale_series(one)
    pr = []
    for k, (nm, a, b) in enumerate(oc.YEARS):
        x = sc[(sc.index >= a)].iloc[:1000].mean() * 10.0           # the first ~day of the year
        th = min(GRID, key=lambda g: abs(g - x)); pr.append(th)
    pr_r = [tab[pr[k]][k] for k in range(len(names))]
    print('   依年初價格：' + '  '.join(f'{names[k]} 用 {pr[k]:g} 點 → {pr_r[k]:+.0f}R' for k in range(len(names)))
          + f'；樣本外 4 年合計 {sum(pr_r[:4]):+.0f}R（固定 10 點 {sum(tab[10.0][:4]):+.0f}R）')


def main():
    tfs = [int(a) for a in sys.argv[1:] if a.isdigit()] or [2, 5]
    one = oc.load(); M = oc.Market(one)
    print('每年固定一個 Trend Judge 門檻（一般 X 點、強 3.5X 點），其他照 v3；每筆扣 1 點、一次一筆')
    for tf in tfs:
        run(one, M, tf, 3.0 if tf == 2 else 2.0)


if __name__ == '__main__':
    main()
