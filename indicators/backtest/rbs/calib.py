"""Calibrating the Trend Judge thresholds across years (NQ was ~12-16k in 2022, ~30k in 2026).

  cd indicators/backtest
  python3 -I rbs/calib.py [mech | calib | all]          # default all

Remi's idea (2026-10-20): a fixed 10 / 35 point threshold means far stronger trends when NQ was half the price, so
the signals came late in the move. Two parts:
  mech   the mechanism: v3 trend signals by Trend Judge spread at the signal, in points and as a multiple of the
         day's calibration, per year -- were the losing years' losses in the large-spread (late) signals?
  calib  thresholds that follow the market, known in advance (trailing 20 sessions up to the day before), normalised
         so the v3 year averages 10 / 35 points (NQ RTH 20 / 40):
           價格       real NQ price (the pre-registered variant from oos_plan.md, already run)
           振幅       average daily range in points
           差值       median |Trend Judge spread| in points
         each for NQ 2m / 5m / 3m and NQ RTH, per year, v3 frozen otherwise (MIX boxes use the same threshold).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def daily_factor(one, stat):
    """Per-minute factor = trailing 20-session mean of a daily statistic (up to the previous session) divided by its mean
    over the v3 year."""
    et = one.index.tz_convert(ss.NY)
    sess = (et + pd.Timedelta(hours=6)).date                        # 18:00 New York opens the next session
    if stat == 'range':
        g = pd.DataFrame({'h': one.high.values, 'l': one.low.values, 's': sess}).groupby('s')
        d = g.h.max() - g.l.min()
    else:                                                            # median |Trend Judge spread| of the session
        tdm = mm.minute_trend(one)
        d = pd.Series(np.abs(tdm['diff'].values), index=sess).groupby(level=0).median()
    trail = d.rolling(20, min_periods=10).mean().shift(1)
    ins = (pd.Index(trail.index) >= pd.Timestamp(oc.YEARS[-1][1]).date()) & (pd.Index(trail.index) <= pd.Timestamp(oc.YEARS[-1][2]).date())
    f = trail / trail[ins].mean()
    return pd.Series(pd.Series(f).reindex(sess).values, index=one.index).ffill().bfill()


def mech(one):
    M = oc.Market(one); C = M.ctx(2); df = C.df
    s = oc.trend_set(df, M.H, 2, 20, df.thr.values, 3.0, 0, 180)
    fr = daily_factor(one, 'range').reindex(pd.DatetimeIndex(df.last_min)).values
    s = s.assign(rel=s.spread.values / fr[s.i])
    print('## 機制：v3 趨勢訊號（NQ 2m）依訊號時的 Trend Judge 差值；每格 筆數 / 1R 勝率 / 3R 每筆')
    for col, bins, lab in (('spread', ((10, 20), (20, 35), (35, 60), (60, 999)), '差值（點）'),
                           ('rel', ((0, 20), (20, 35), (35, 60), (60, 999)), '差值 ÷ 振幅倍數（換算成 v3 那年的點數）')):
        print(f'   {lab}')
        heads = [f'{lo}–' + (str(hi) if hi < 999 else '以上') for lo, hi in bins]
        print(f'   {"":<16}' + ''.join(f'{h:>22}' for h in heads))
        for nm, a, b in oc.YEARS:
            z = s[(s.date >= a) & (s.date <= b)]
            cells = []
            for lo, hi in bins:
                y = z[(z[col] >= lo) & (z[col] < hi)]
                cells.append(f'{len(y):4d} {100 * (y.r1 > 0).mean():4.0f}% {(y.r3 - 1 / y.risk).mean():+5.2f}' if len(y) else f'{0:4d}')
            print(f'   {nm:<16}' + ''.join(f'{c:>22}' for c in cells))


def calib(one):
    print('\n## 門檻校正（每年 R：Y1 Y2 Y3 Y4 IS；每年門檻平均是 v3 那年的幾倍）')
    facs = {'原版（固定點數）': None, '價格': oc.scale_series(one), '振幅': daily_factor(one, 'range'), '差值': daily_factor(one, 'tjdiff')}
    for nm, f in facs.items():
        if f is None: continue
        print(f'   {nm}：' + '  '.join(f'{y[:2]} ×{f[(f.index >= a) & (f.index <= b + " 23:59")].mean():.2f}' for y, a, b in oc.YEARS))
    for tf, R, lo, hi, mix in ((2, 3.0, 0, 180, True), (5, 2.0, 0, 180, True), (3, 1.0, 90, 120, False)):
        print(f'   NQ {tf}m')
        for nm, f in facs.items():
            oc.one_line(f'　{nm}', oc.Market(one, f).nq(tf, R, lo, hi, mix=mix))
    print('   NQ RTH 1m')
    for nm, f in facs.items():
        oc.one_line(f'　{nm}', oc.nq_rth(one, f))


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    one = oc.load()
    if what in ('mech', 'all'): mech(one)
    if what in ('calib', 'all'): calib(one)


if __name__ == '__main__':
    main()
