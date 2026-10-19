"""Are the QQQ 1-minute trend signals good because NQ 2 minutes is trending the same way at the time?

  cd indicators/backtest
  python3 -I rbs/qqq_vs_nq.py

QQQ 1m = NQ bars cut to the cash session (market_matrix.py's QQQ stand-in), two signal sets:
  ETF 設定     (35, 0, 8, 1), threshold 20 NQ points (QQQ 0.5), distance 7 ATR (Remi Superb v3 on QQQ)
  趨勢 0–180   (20, 0, 8, 1), threshold 10, distance 3 ATR, trend minutes 0-180
NQ 2m = the 24-hour NQ chart (threshold 10), read at the last 2-minute bar that has closed by the QQQ entry:
  Trend Judge state against the QQQ trade (same side / MIX / opposite), its trend minutes, and whether a NQ 2m
  filtered alert on the same side came in the last 10 or 30 minutes. Everything is known at the entry.
Each QQQ signal on its own (1 NQ point cost); 前 / 後 = the two halves of the dates.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm


def table(nm, y, cost, split):
    print(f'   {nm:<26} ' + mm.row_ind(y, cost, split))


def main():
    cost = 1.0
    nq1 = mm.load_market('nq', [])
    q1 = mm.load_market('qqq', [])
    # NQ 2m, 24-hour chart
    tdn = mm.minute_trend(nq1); Hn = mm.hourly(nq1, False)
    dn = mm.chart(nq1, tdn, 2, 10.0, 35.0)
    sn = mm.trend_signals(dn, Hn, 2)
    fn = sn[mm.filt(sn, 10.0)]
    nclose = (pd.DatetimeIndex(dn.last_min) + pd.Timedelta(minutes=1)).values.astype('datetime64[ns]').astype(np.int64)
    ndir = np.sign(dn.tj_dir.values); ntm = dn.tmin.values
    fts = {sd: np.sort((pd.DatetimeIndex(dn.last_min.values[fn.i[fn.side == sd]]).tz_localize('UTC') + pd.Timedelta(minutes=1))
                       .values.astype('datetime64[ns]').astype(np.int64)) for sd in (1, -1)}
    # QQQ 1m
    tdq = mm.minute_trend(q1); Hq = mm.hourly(q1, True)
    dq = mm.chart(q1, tdq, 1, 20.0, 40.0)
    sets = {}
    s_etf = mm.trend_signals(dq, Hq, 1, 35, 8)
    sets['ETF 設定 (35, 0, 8, 1)'] = s_etf[mm.filt(s_etf, 20.0, 7.0)]
    dq10 = mm.chart(q1, tdq, 1, 10.0, 35.0)
    s_std = mm.trend_signals(dq10, Hq, 1)
    f_std = s_std[mm.filt(s_std, 10.0)]
    sets['趨勢 0–180 分 (20, 0, 8, 1)'] = f_std[(f_std.tm >= 0) & (f_std.tm < 180)]
    print('QQQ 1 分 K 的趨勢訊號 × 同一時間 NQ 2 分 K（24 小時圖）的狀態；每筆扣 1 點（NQ 點）')
    print(f'{"":<29}  筆數   1R 勝率 每筆   2R 勝率 每筆   3R 勝率 每筆')
    for name, y in sets.items():
        d_ = dq if name.startswith('ETF') else dq10
        t = (pd.DatetimeIndex(d_.last_min.values[y.i]).tz_localize('UTC') + pd.Timedelta(minutes=1)).values.astype('datetime64[ns]').astype(np.int64)
        k = np.searchsorted(nclose, t, 'right') - 1                      # last NQ 2m bar closed by the QQQ entry
        rel = ndir[k] * y.side.values
        y = y.assign(nrel=rel, ntm=np.where(rel > 0, ntm[k], np.nan))
        for w in (10, 30):
            win = w * 60 * 10 ** 9
            y[f'nsig{w}'] = [(lambda arr: (np.searchsorted(arr, tt, 'right') - np.searchsorted(arr, tt - win, 'right')) > 0)(fts[sd])
                             for tt, sd in zip(t, y.side.values)]
        d = sorted(y.date.unique()); split = d[len(d) // 2]
        print(f'\n  ## {name}')
        table('全部', y, cost, split)
        table('NQ 2m Trend Judge 同向', y[y.nrel > 0], cost, split)
        table('NQ 2m 是 MIX', y[y.nrel == 0], cost, split)
        table('NQ 2m 反向', y[y.nrel < 0], cost, split)
        table('　同向，NQ 趨勢 0–180 分', y[(y.nrel > 0) & (y.ntm < 180)], cost, split)
        table('　同向，NQ 趨勢 180 分以上', y[(y.nrel > 0) & (y.ntm >= 180)], cost, split)
        table('前 10 分鐘有 NQ 2m 同向過濾訊號', y[y.nsig10], cost, split)
        table('前 30 分鐘有 NQ 2m 同向過濾訊號', y[y.nsig30], cost, split)
        table('前 30 分鐘沒有', y[~y.nsig30], cost, split)
        print('   一次一筆（3R / 2R，每年）')
        for nm2, z in (('全部', y), ('去掉 NQ 2m 反向', y[y.nrel >= 0]), ('NQ 2m 同向且趨勢 0–180 分', y[(y.nrel > 0) & (y.ntm < 180)])):
            for R in (3.0, 2.0):
                tq = mm.ss.seq(z.sort_values('i'), R)
                nn = tq[f'r{R:g}'].values - cost / tq.risk.values
                eq = np.cumsum(nn); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0.0
                mo = pd.Series(nn).groupby(tq.month.values).sum()
                print(f'     {nm2:<24} {R:g}R {len(tq):4d} 筆  勝率 {100 * (tq[f"r{R:g}"] > 0).mean():4.1f}%  每筆 {nn.mean():+.3f}R  一年 {nn.sum():+6.1f}R  回撤 {dd:4.1f}R  賺錢月份 {(mo > 0).sum()}/{len(mo)}')



def pine_way():
    """Remi Superb v3's QQQ filter as the indicator computes it: Trend Judge from NQ 2m closes (chart bars, 24 / 8
    EMA steps per bar), the previous completed 2m bar (request.security(..., expr[1], lookahead_on))."""
    nq1 = mm.load_market('nq', []); q1 = mm.load_market('qqq', [])
    dn = mm.chart(nq1, mm.minute_trend(nq1), 2, 10.0, 35.0)
    c = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0))
    nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    dq = mm.chart(q1, mm.minute_trend(q1), 1, 20.0, 40.0)
    s = mm.trend_signals(dq, mm.hourly(q1, True), 1, 35, 8); y = s[mm.filt(s, 20.0, 7.0)].sort_values('i')
    t_open = pd.DatetimeIndex(dq.last_min.values[y.i]).tz_localize('UTC').values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(nstart, t_open, 'right') - 2                  # the NQ 2m bar before the one holding this bar
    rel = ndir[k] * y.side.values
    print('\n######## v3 在 QQQ 上的算法（NQ 2m K 棒推算、上一根已收完），一次一筆 3R')
    for nm, z in (('全部', y), ('NQ 2m 不反向（v3 預設）', y[rel >= 0]), ('NQ 2m 反向', y[rel < 0])):
        tq = mm.ss.seq(z, 3.0); nn = tq.r3.values - 1.0 / tq.risk.values
        eq = np.cumsum(nn); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0.0
        mo = pd.Series(nn).groupby(tq.month.values).sum()
        print(f'   {nm:<20} {len(tq):4d} 筆  勝率 {100 * (tq.r3 > 0).mean():4.1f}%  每筆 {nn.mean():+.3f}R  一年 {nn.sum():+6.1f}R  回撤 {dd:4.1f}R  賺錢月份 {(mo > 0).sum()}/{len(mo)}')


if __name__ == '__main__':
    main()
    pine_way()
