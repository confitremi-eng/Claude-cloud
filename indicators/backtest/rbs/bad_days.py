"""Which days did v3 (NQ 2m) lose on in the earlier years? Day of week, holidays, FOMC, jobs report, expiry, month end.

  cd indicators/backtest
  python3 -I rbs/bad_days.py

v3 frozen, one at a time, 3R; R per New York trading day. Day tags: weekday; NYSE closed (futures still trade) or early
close; the day before / after an NYSE holiday; FOMC day; first Friday (jobs report, approximately); third Friday
(monthly options expiry); last trading day of the month. Out of sample (2021-10 .. 2025-10) and the v3 year. Also
the losing streaks (3+ losing days in a row) and the worst 10% of days: which tags show up more than usual.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def tags(days):
    d = pd.to_datetime(pd.Series(days))
    closed = set(mm.NYSE_CLOSED); early = set(mm.EARLY_CLOSE)
    hol = sorted(pd.to_datetime(list(closed)))
    bdays = pd.bdate_range('2021-10-01', '2026-10-31')
    nxt = {}; prv = {}
    for h in hol:
        i = bdays.searchsorted(h)
        if i > 0: prv[bdays[i - 1].strftime('%Y-%m-%d')] = True
        j = i + 1 if i < len(bdays) and bdays[i] == h else i
        if j < len(bdays): nxt[bdays[j].strftime('%Y-%m-%d')] = True
    s = d.dt.strftime('%Y-%m-%d')
    out = pd.DataFrame({'date': s})
    out['wd'] = d.dt.weekday
    out['closed'] = s.isin(closed); out['early'] = s.isin(early)
    out['pre_hol'] = s.map(lambda x: x in prv); out['post_hol'] = s.map(lambda x: x in nxt)
    out['fomc'] = s.isin(ss.FOMC)
    out['nfp'] = (d.dt.weekday == 4) & (d.dt.day <= 7)
    out['opex'] = (d.dt.weekday == 4) & (d.dt.day >= 15) & (d.dt.day <= 21)
    me = d.groupby(d.dt.strftime('%Y-%m')).transform('max')
    out['month_end'] = d == me
    return out


def main():
    one = oc.load(); M = oc.Market(one)
    t = M.nq(2, 3.0, 0, 180)
    day = t.groupby('date').net.sum()
    day = day[(day.index >= '2021-10-15') & (day.index <= '2026-10-14')]
    f = tags(day.index).set_index('date'); f['R'] = day
    f['p'] = np.where(f.index >= '2025-10-15', 'v3 那年', '樣本外')
    labels = [('wd', 0, '週一'), ('wd', 1, '週二'), ('wd', 2, '週三'), ('wd', 3, '週四'), ('wd', 4, '週五'), ('wd', 6, '週日（晚上開盤）'),
              ('closed', True, '美股休市日（期貨照常）'), ('early', True, '美股提早收盤'), ('pre_hol', True, '美股休市前一天'),
              ('post_hol', True, '美股休市後一天'), ('fomc', True, 'FOMC 日'), ('nfp', True, '每月第一個週五（非農）'),
              ('opex', True, '第三個週五（選擇權結算）'), ('month_end', True, '月底最後一天')]
    print('v3 NQ 2m 每天的 R（一次一筆、3R），依日子分組：天數、平均每天 R、虧錢的天數比例')
    print(f'   {"":<22} {"樣本外 2021/10–2025/10":>30} {"v3 那年":>26}')
    for col, val, lab in labels:
        cells = []
        for p in ('樣本外', 'v3 那年'):
            z = f[(f.p == p) & (f[col] == val)]
            cells.append(f'{len(z):4d} 天 {z.R.mean():+6.2f}R  虧 {100 * (z.R < 0).mean():4.0f}%' if len(z) else '   0 天')
        print(f'   {lab:<22} {cells[0]:>30} {cells[1]:>26}')
    base = f[f.p == '樣本外']
    print(f'   {"全部":<22} {len(base):4d} 天 {base.R.mean():+6.2f}R  虧 {100 * (base.R < 0).mean():4.0f}%')
    # losing streaks
    lose = (base.R < 0).values; streak_days = np.zeros(len(base), bool); k = 0
    for i in range(len(lose)):
        k = k + 1 if lose[i] else 0
        if k >= 3: streak_days[i - k + 1:i + 1] = True
    worst = base.R <= base.R.quantile(0.10)
    print('\n樣本外：連續虧 3 天以上的日子、最差 10% 的日子，各種日子的比例（和全部日子比）')
    print(f'   {"":<22} {"全部日子":>8} {"連虧 3 天+":>10} {"最差 10%":>9}')
    for col, val, lab in labels:
        a = 100 * (base[col] == val).mean(); b = 100 * (base[col][streak_days] == val).mean(); c = 100 * (base[col][worst] == val).mean()
        print(f'   {lab:<22} {a:7.1f}% {b:9.1f}% {c:8.1f}%')
    print(f'   連虧 3 天以上的日子 {streak_days.sum()} 天（{100 * streak_days.mean():.0f}%），最差 10% {worst.sum()} 天（每天 ≤ {base.R.quantile(0.10):+.1f}R）')


if __name__ == '__main__':
    main()
