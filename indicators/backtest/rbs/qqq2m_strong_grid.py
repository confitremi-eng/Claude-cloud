"""QQQ 2m (NQ cash-session 2m bars stand in) in a strong trend, no other filters: which (stage, 0, EMA, 1) works best?

  cd indicators/backtest
  python3 -I rbs/qqq2m_strong_grid.py

Strong = Trend Judge (cash-session data) beyond 40 points on the signal's side at the signal bar. Only raw original
signals on that side; nothing else (no 1h, ATR, slow-line, event or time filters). Each signal on its own: entry at the
close, stop at the two-bar extreme, targets 1R / 2R / 3R within 60 bars or the session end, 1 point cost.
Shows the v3 year (2025-10 .. 2026-10) and the four years before, per trade and 1R hit rate; plus one at a time 3R per year.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc

STAGES = (10, 15, 20, 25, 30, 35, 40, 50)
EMAS = (5, 8, 11, 13)


def main():
    one = oc.load()
    cash = mm.cash_only(one); tdm = mm.minute_trend(cash); H = mm.hourly(cash, True)
    df = oc.chart(cash, tdm, 2, 20.0, 40.0)
    split = oc.YEARS[3][2]
    res = {}
    for st in STAGES:
        for em in EMAS:
            s = mm.trend_signals(df, H, 2, st, em)
            s = s[s.spread > 40].copy()
            for R in (1, 2, 3): s[f'n{R}'] = s[f'r{R}'] - oc.COST / s.risk
            res[(st, em)] = s
    for title, fn in (('v3 那年 1R 勝率', lambda z: f'{100 * (z[z.date > split].r1 > 0).mean():5.0f}%'),
                      ('v3 那年每筆 1R', lambda z: f'{z[z.date > split].n1.mean():+6.2f}'),
                      ('v3 那年每筆 2R', lambda z: f'{z[z.date > split].n2.mean():+6.2f}'),
                      ('v3 那年每筆 3R', lambda z: f'{z[z.date > split].n3.mean():+6.2f}'),
                      ('前 4 年每筆 1R', lambda z: f'{z[z.date <= split].n1.mean():+6.2f}'),
                      ('前 4 年每筆 3R', lambda z: f'{z[z.date <= split].n3.mean():+6.2f}'),
                      ('v3 那年筆數', lambda z: f'{(z.date > split).sum():6d}')):
        print(f'\n## {title}（列：階段，欄：EMA）')
        print('        ' + ''.join(f'  EMA {e:<3}' for e in EMAS))
        for st in STAGES:
            print(f'   {st:>3}  ' + ''.join(f'  {fn(res[(st, e)]):>7}' for e in EMAS))
    print('\n## 一次一筆，每年合計 R（勝率）')
    for st, em, R in ((20, 8, 3.0), (20, 11, 3.0), (35, 8, 3.0), (20, 11, 1.0), (35, 8, 1.0), (50, 8, 3.0)):
        t = ss.seq(res[(st, em)].sort_values('i'), R); col = f'r{R:g}'
        tt = pd.DataFrame({'date': t.date.values, 'R': t[col].values, 'net': t[col].values - oc.COST / t.risk.values})
        print(f'   ({st}, 0, {em}, 1) {R:g}R：' + '  '.join(f'{nm[:2]} {z.net.sum():+5.0f}R（{100 * (z.R > 0).mean():.0f}%）' for nm, a, b in oc.YEARS for z in [tt[(tt.date >= a) & (tt.date <= b)]]))


if __name__ == '__main__':
    main()
