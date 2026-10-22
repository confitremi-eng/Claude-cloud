"""Big gap-down mornings, five years: the three long candidates found on one year of data, per year at 1R and 2R.

  cd indicators/backtest
  python3 -I rbs/gapdown_5y.py [data/NQ_1m_5y.csv]

NQ cash-session 1m bars stand in for QQQ. Gap = 09:30 open vs the previous day's 15:59 close. Years as in oos_check
(Oct-Oct; the last one runs to the end of the data). Each cell: 1R or 2R win rate / net R (1 point cost) / trades.
  A. ORB 5 (gapdown_long.py): first 1m close above the first 5 minutes' high, 09:45-12:00, stop the day's low so far,
     one per day, flat at 16:00.
  B. v3 raw buys (gapdown_v3_longs.py): (35, 0, 8, 1) buy signals 09:45-12:00, trend filters off; only stop >= 0.95 ATR,
     slow line <= 7 ATR, event windows, FOMC days. Two-bar stop, one at a time.
  C. Gap fill (gapfill_1m.py): raw (35, 0, -, 0) buys 09:45-12:00 before the gap fills, two-bar stop, one at a time.
Controls: the same rules on days without a gap down (gap > -0.3%; B uses |gap| <= 0.3% as in its script).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import gapdown_long as gl
import gapdown_v3 as gv
import gapfill_1m as gf

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'data', 'NQ_1m_5y.csv')
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print(f'{os.path.basename(path)}，每格：勝率 / 淨 R / 筆數')
    print(f'   {"":<34}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>19}' for nm, a, b in yrs) + f'{"合計":>19}')

    def row(lab, t, rcol, ncol):
        cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
        print(f'   {lab:<34}' + ''.join(f'{100 * (z[rcol] > 0).mean() if len(z) else 0:6.0f}% {z[ncol].sum():+5.1f}R {len(z):3d}' for z in cells), flush=True)

    # A. ORB 5
    t, _ = gl.build(gl.load(path)); o = t[t.setup == 'ORB 5']
    print('\nA. ORB 5（停損當天低點，每天一筆）')
    for gm, lab in ((-0.75, '缺口 ≤ −0.75%'), (-0.5, '缺口 ≤ −0.5%'), (None, '對照：缺口 > −0.3%')):
        z = o[o.gap > -0.3] if gm is None else o[o.gap <= gm]
        row(f'{lab} 1R', z, 'r1', 'n1'); row(f'{lab} 2R', z, 'r2', 'n2')

    # B. v3 raw buys, trend filters off
    one = mm.read_csv(path); one['bad'] = False
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    df = mm.chart(cash, tdq, 1, 20.0, 40.0)
    s = mm.trend_signals(df, Hq, 1, 35, 8)
    et = pd.DatetimeIndex(df.datetime.values[s.i.values]); et = (et.tz_localize('UTC') if et.tz is None else et).tz_convert(ss.NY) + pd.Timedelta(minutes=1)
    s['emin'] = np.asarray(et.hour * 60 + et.minute); s['day'] = et.strftime('%Y-%m-%d')
    s['gap'] = s.day.map(gv.day_gaps(cash))
    keep = (s.side == 1) & (s.emin >= 585) & (s.emin < 720) & ~s.date.isin(ss.FOMC) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 7.0)
    print('\nB. v3 原始買訊，不看 TJ / 1h / NQ 2m（兩根停損，一次一筆）')
    for gm, lab in ((-0.75, '缺口 ≤ −0.75%'), (-0.5, '缺口 ≤ −0.5%'), (None, '對照：平開 ±0.3%')):
        z = s[keep & ((s.gap.abs() <= 0.3) if gm is None else (s.gap <= gm))].sort_values('i')
        for R in (1.0, 2.0):
            q = ss.seq(z, R).copy(); q['n'] = q[f'r{R:g}'] - oc.COST / q.risk
            row(f'{lab} {R:g}R', q.assign(date=q.day), f'r{R:g}', 'n')

    # C. gap fill, raw (35, 0, -, 0)
    g1 = gl.load(path).reset_index(); days = {}; prev = None
    for d, g in g1.groupby('day', sort=True):
        a, b = g.index[0], g.index[-1] + 1
        if prev is not None: days[d] = (a, b, prev, 100 * (g1.open.values[a] / prev - 1))
        prev = g1.close.values[b - 1]
    print('\nC. 補缺口：(35, 0, -, 0) 原始買訊，缺口還沒補之前（兩根停損，一次一筆）')
    win = ('09:45–12:00', 585, 720)
    for gm, lab in ((-0.75, '缺口 ≤ −0.75%'), (-0.5, '缺口 ≤ −0.5%')):
        for tk in ('1R', '2R'):
            z = gf.run(g1, days, 35, 0, gm, '兩根低點', tk, win)
            row(f'{lab} {tk}', z, 'r', 'net')


if __name__ == '__main__':
    main()
