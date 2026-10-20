"""Which months suited Remi Superb v3? Monthly R over five years (2021-10 .. 2026-10) against the month's market.

  cd indicators/backtest
  python3 -I rbs/v3_months.py

v3 frozen (rbs/oos_check.py): NQ 2m, NQ 5m, NQ RTH 1m, one position at a time, 1 point cost. For each calendar month:
R of each, and the NQ month: return %, realized volatility (daily returns, annualised), average daily range %,
trend efficiency (|month move| / sum of |daily moves|), share of 2m bars with Trend Judge trending.
Prints the monthly table, calendar-month averages, R by tercile of each feature (same month: what kind of month it
was), and by tercile of the previous month's feature (could it have been known in advance?).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc


def month_features(one, C2):
    et = one.index.tz_convert(ss.NY)
    day = pd.Series(one.close.values, index=et).resample('1D').last().dropna()
    hi = pd.Series(one.high.values, index=et).resample('1D').max().reindex(day.index)
    lo = pd.Series(one.low.values, index=et).resample('1D').min().reindex(day.index)
    real = pd.Series(one.close.values - oc.real_price(one.index), index=et).resample('1D').last().reindex(day.index)
    dr = day.diff()
    f = pd.DataFrame({'ret': dr / real.shift(), 'rng': (hi - lo) / real, 'absmove': dr.abs(), 'move': dr})
    f['m'] = f.index.strftime('%Y-%m')
    g = f.groupby('m')
    out = pd.DataFrame({'ret': g.ret.sum() * 100, 'vol': g.ret.std() * np.sqrt(252) * 100, 'rng': g.rng.mean() * 100,
                        'eff': g.move.sum().abs() / g.absmove.sum()})
    d2 = C2.df; tr = (d2.tj_dir.values != 0) & d2.tradable.values
    out['trend'] = pd.Series(tr, index=d2.datetime.dt.tz_convert(ss.NY).dt.strftime('%Y-%m').values).groupby(level=0).mean() * 100
    return out


def tercile_table(df, col, rcols, label, shift=False):
    x = df[col].shift(1) if shift else df[col]
    ok = x.notna()
    q = pd.qcut(x[ok], 3, labels=['低', '中', '高'])
    print(f'   {label:<18} ' + '   '.join(
        f'{t}（{x[ok][q == t].min():.1f}–{x[ok][q == t].max():.1f}）: ' + ' / '.join(f'{df.loc[ok][q == t][c].mean():+5.1f}' for c in rcols)
        for t in ('低', '中', '高')))


def main():
    one = oc.load(); M = oc.Market(one)
    t2 = M.nq(2, 3.0, 0, 180); t5 = M.nq(5, 2.0, 0, 180); tr = oc.nq_rth(one)
    mon = pd.DataFrame({'2m': t2.groupby(t2.date.str[:7]).net.sum(), '5m': t5.groupby(t5.date.str[:7]).net.sum(),
                        'RTH': tr.groupby(tr.date.str[:7]).net.sum()}).fillna(0)
    mon = mon.join(month_features(one, M.ctx(2)), how='left')
    mon = mon[(mon.index >= '2021-11') & (mon.index <= '2026-09')]          # full months only
    rc = ['2m', '5m', 'RTH']
    print('v3 每月 R（NQ 2m / 5m / NQ RTH），和 NQ 當月：漲跌%、年化波動%、日均振幅%、趨勢效率、Trend Judge 有趨勢的時間%')
    print(f'   {"月份":<8} {"2m":>6} {"5m":>6} {"RTH":>6}   {"漲跌":>6} {"波動":>5} {"振幅":>5} {"效率":>5} {"趨勢":>5}')
    for m, r in mon.iterrows():
        mark = ' ←' if m >= '2025-10' else ''
        print(f'   {m:<8} {r["2m"]:+6.1f} {r["5m"]:+6.1f} {r["RTH"]:+6.1f}   {r.ret:+6.1f} {r.vol:5.1f} {r.rng:5.2f} {r.eff:5.2f} {r.trend:5.1f}{mark}')
    pos = (mon[rc] > 0).sum()
    print(f'\n賺錢的月份：2m {pos["2m"]}/{len(mon)}、5m {pos["5m"]}/{len(mon)}、RTH {pos["RTH"]}/{len(mon)}；'
          f'原樣本前（2021-11 .. 2025-09）2m 賺錢月 {(mon.loc[mon.index < "2025-10", "2m"] > 0).sum()}/{(mon.index < "2025-10").sum()}')
    print('\n## 日曆月份平均 R（2m / 5m / RTH；括號是 2m 賺錢的年數）')
    cal = mon.copy(); cal['cm'] = [m[5:] for m in cal.index]
    for cm, g in cal.groupby('cm'):
        print(f'   {cm} 月：' + ' / '.join(f'{g[c].mean():+6.1f}' for c in rc) + f'   （{(g["2m"] > 0).sum()}/{len(g)}）')
    pre = mon[mon.index < '2025-10']
    print('\n## 同一個月的行情型態 → 當月平均 R（2m / 5m / RTH），只用原樣本以前的 47 個月')
    for col, lab in (('ret', '當月漲跌 %'), ('vol', '年化波動 %'), ('rng', '日均振幅 %'), ('eff', '趨勢效率'), ('trend', 'TJ 有趨勢時間 %')):
        tercile_table(pre, col, rc, lab)
    print('\n## 上個月的行情型態 → 這個月平均 R（能不能事先知道），原樣本以前')
    for col, lab in (('ret', '上月漲跌 %'), ('vol', '上月波動 %'), ('rng', '上月振幅 %'), ('eff', '上月趨勢效率'), ('trend', '上月 TJ 趨勢 %'),
                     ('2m', '上月 2m 的 R')):
        tercile_table(pre, col, rc, lab, shift=True)
    print('\n## 原樣本那一年的行情型態（對照）')
    ins = mon[mon.index >= '2025-10']
    print('   平均：' + '  '.join(f'{lab} {ins[c].mean():.2f}' for c, lab in (('ret', '漲跌%'), ('vol', '波動%'), ('rng', '振幅%'), ('eff', '效率'), ('trend', 'TJ趨勢%')))
          + '\n   之前：' + '  '.join(f'{lab} {pre[c].mean():.2f}' for c, lab in (('ret', '漲跌%'), ('vol', '波動%'), ('rng', '振幅%'), ('eff', '效率'), ('trend', 'TJ趨勢%'))))


if __name__ == '__main__':
    main()
