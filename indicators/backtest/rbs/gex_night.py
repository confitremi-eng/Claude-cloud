"""v3 trades vs the QQQ gamma flip, hour by hour incl. the night session (ZeroGEX hourly, 2026-06-29 onward).

  cd indicators/backtest
  python3 -I rbs/zerogex_fetch.py "../../ZEROGEX API.txt" hourly     # data/zerogex/QQQ_hourly.csv
  python3 -I rbs/gex_night.py

Each hourly bucket is the last snapshot inside that hour, so it is used from the end of the hour (as if checked once an
hour). At each v3 entry: the latest QQQ flip known then (at most 4 hours old, else "no data"), turned into NQ points with
the NQ / QQQ ratio at that snapshot. Toward = the flip lies in the trade's direction (buy below the flip, sell above).
v3 as now (FOMC days off), NQ 2m 3R and 5m 2R, one at a time. Cash session = 09:30-16:00 New York entries.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc
import v3_kline as vk

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = '2026-06-29'


def row(lab, t):
    if not len(t): print(f'   {lab:<22}    0 筆'); return
    print(f'   {lab:<22} {len(t):4d} 筆 勝 {100 * (t.net > 0).mean():3.0f}% 合計 {t.net.sum():+6.1f}R 每筆 {t.net.mean():+.2f}R')


def main():
    g = pd.read_csv(os.path.join(HERE, 'data', 'zerogex', 'QQQ_hourly.csv')).dropna(subset=['gamma_flip', 'spot'])
    g['known'] = pd.to_datetime(g.ts, utc=True) + pd.Timedelta(hours=1)
    one = oc.load(); M = oc.Market(one)
    nq = one.close.sort_index()
    g['nq'] = nq.reindex(g.known - pd.Timedelta(minutes=1), method='ffill').values
    g['flip_nq'] = g.gamma_flip * g.nq / g.spot
    g = g.dropna(subset=['flip_nq']).sort_values('known')
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df
        T = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180); T = T[~T.date.isin(ss.FOMC)]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        t = vk.trades(C, T, mix, R); t = t[t.date >= START].copy()
        t['tin'] = (df.datetime.values[t.i.values] + pd.Timedelta(minutes=tf)).tz_convert('UTC') if hasattr(df.datetime.values[0], 'tz') else pd.to_datetime(df.datetime.values[t.i.values], utc=True) + pd.Timedelta(minutes=tf)
        t = t.sort_values('tin')
        m = pd.merge_asof(t, g[['known', 'flip_nq', 'gamma_flip']], left_on='tin', right_on='known', direction='backward')
        age = (m.tin - m.known).dt.total_seconds() / 3600
        m.loc[age > 4, 'flip_nq'] = np.nan
        et = m.tin.dt.tz_convert(ss.NY); mi = et.dt.hour * 60 + et.dt.minute
        m['cash'] = (mi > 570) & (mi <= 960) & (et.dt.weekday < 5)
        m['toward'] = np.sign(m.flip_nq - m.entry) == m.side
        m['dist'] = (m.flip_nq - m.entry).abs()
        print(f'\nNQ {tf}m（{R:g}R，{START} 起）')
        for lab, z in (('夜盤', m[~m.cash]), ('現金盤', m[m.cash]), ('全部', m)):
            has = z.flip_nq.notna()
            print(f' {lab}')
            row('全部', z); row('朝 flip 走', z[has & z.toward]); row('離開 flip', z[has & ~z.toward]); row('沒有 flip 資料', z[~has])
            for lo, hi in ((0, 100), (100, 300), (300, 1e9)):
                y = z[has & (z.dist >= lo) & (z.dist < hi)]
                if len(y): print(f'      離 flip {lo:g}–{hi:g} 點：朝 {y.toward.sum()} 筆 {y[y.toward].net.mean():+.2f}R；離開 {(~y.toward).sum()} 筆 {y[~y.toward].net.mean():+.2f}R')
        nt = m[~m.cash & m.flip_nq.notna()]
        print('   夜盤每月（朝 / 離開，R）：' + '  '.join(f'{k[5:]}月 {v[v.toward].net.sum():+.0f}/{v[~v.toward].net.sum():+.0f}' for k, v in nt.groupby(nt.date.str[:7])))


if __name__ == '__main__':
    main()
