"""Were other timeframes better in the earlier years? v3 rules on NQ 1 / 2 / 3 / 5 minutes, year by year.

  cd indicators/backtest
  python3 -I rbs/tf_years.py [1 2 3 5]          # default all four

Same frozen v3 rules on every timeframe (Trend Judge > 10 / 35, 1-hour EMA20, stop >= 1 ATR, <= 3 ATR from the slow
line, events, trend 0-180 minutes; MIX 60-minute box, 10% break within 60 minutes, stop at the middle, no MIX 16-20
New York; Friday cut-off; one at a time, 60-bar exit, 17:00 halt; 1 point cost). Rows: trend + MIX, trend only, MIX
only, each at 1R / 2R / 3R, plus v3's own 3m (trend 90-120, 1R). Columns: R per year (Y1-Y4 out of sample, IS = the
v3 year), out-of-sample R per trade, profitable out-of-sample years.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oos_check as oc


def main():
    tfs = [int(a) for a in sys.argv[1:] if a.isdigit()] or [1, 2, 3, 5]
    one = oc.load(); M = oc.Market(one)
    print('NQ 各週期套 v3 規則，每年 R：' + '  '.join(nm[:2] for nm, a, b in oc.YEARS) + '；每筆扣 1 點、一次一筆')
    for tf in tfs:
        print(f'\n## NQ {tf} 分 K')
        for R in (1.0, 2.0, 3.0):
            oc.one_line(f'趨勢 + MIX，{R:g}R', M.nq(tf, R, 0, 180))
            oc.one_line(f'只有趨勢，{R:g}R', M.nq(tf, R, 0, 180, mix=False))
            oc.one_line(f'只有 MIX，{R:g}R', M.nq(tf, R, 0, 180, trend=False))
        if tf == 3:
            oc.one_line('v3 的 3m（趨勢 90–120，1R）', M.nq(3, 1.0, 90, 120, mix=False))
        M._c.clear()


if __name__ == '__main__':
    main()
