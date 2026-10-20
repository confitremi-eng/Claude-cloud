"""Short gamma vs long gamma: do v3 trend signals do better when dealers are short gamma? (ZeroGEX hourly, 2026-06-29 on)

  cd indicators/backtest
  python3 -I rbs/gex_regime.py

Idea (Remi): short gamma (price below the flip) -> dealers chase moves -> trend signals better; long gamma (above the
flip) -> dealers damp moves -> trend signals worse, sells especially.
Regime at each entry: NQ entry price vs the latest QQQ flip known then (hourly, used from the end of the hour, at most
4 hours old) in NQ points; also the sign of net GEX in that snapshot. Two views:
  1. v3 trades as taken (one at a time, FOMC days off), trend and MIX apart
  2. every v3 trend signal on its own (more samples, overlapping)
  3. NQ RTH 1m (QQQ setting, cash session only) with the minute-by-minute QQQ flip (ZeroGEX replay, known at the end of
     each minute) as well as the hourly one
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc
import v3_kline as vk
import flip_wait as fw

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = '2026-06-29'


def gex(one):
    g = pd.read_csv(os.path.join(HERE, 'data', 'zerogex', 'QQQ_hourly.csv')).dropna(subset=['gamma_flip', 'spot'])
    g['known'] = pd.to_datetime(g.ts, utc=True) + pd.Timedelta(hours=1)
    nq = one.close.sort_index()
    g['nq'] = nq.reindex(g.known - pd.Timedelta(minutes=1), method='ffill').values
    g['flip_nq'] = g.gamma_flip * g.nq / g.spot
    return g.dropna(subset=['flip_nq']).sort_values('known')


def attach(t, g, df, tf, price):
    t = t.copy(); t['tin'] = pd.to_datetime(df.datetime.values[t.i.values], utc=True) + pd.Timedelta(minutes=tf)
    t['_o'] = np.arange(len(t)); t = t.sort_values('tin')
    m = pd.merge_asof(t, g[['known', 'flip_nq', 'net_gex']], left_on='tin', right_on='known', direction='backward')
    old = (m.tin - m.known).dt.total_seconds() > 4 * 3600
    m.loc[old, ['flip_nq', 'net_gex']] = np.nan
    m['short'] = np.where(m.flip_nq.isna(), np.nan, (m[price] < m.flip_nq).astype(float))
    m['short_net'] = np.where(m.net_gex.isna(), np.nan, (m.net_gex < 0).astype(float))
    et = m.tin.dt.tz_convert(ss.NY); mi = et.dt.hour * 60 + et.dt.minute
    m['cash'] = (mi > 570) & (mi <= 960) & (et.dt.weekday < 5)
    return m


def cell(z):
    return f'{len(z):3d} 筆 勝 {100 * (z.net > 0).mean():3.0f}% {z.net.mean():+.2f}R' if len(z) else '  0 筆'


def table(m, col, title):
    print(f'   {title}')
    print(f'      {"":<10} {"Short gamma":>24} {"Long gamma":>24}')
    for lab, z in (('買', m[m.side == 1]), ('賣', m[m.side == -1]), ('全部', m)):
        print(f'      {lab:<10} {cell(z[z[col] == 1]):>24} {cell(z[z[col] == 0]):>24}')


def main():
    one = oc.load(); M = oc.Market(one); g = gex(one)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df
        T = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180); T = T[~T.date.isin(ss.FOMC)]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        t = vk.trades(C, T, mix, R); t = t[t.date >= START]
        m = attach(t, g, df, tf, 'entry')
        print(f'\nNQ {tf}m（{R:g}R，{START} 起；Short gamma = NQ 在 flip 下方）')
        table(m[m.kind == '趨勢'], 'short', '1. v3 實際做的趨勢單')
        table(m[m.kind == 'MIX'], 'short', '   v3 實際做的 MIX 單')
        Ts = T[T.date >= START].copy(); Ts['net'] = fw.each(C, Ts, R); Ts['entry'] = C.c[Ts.i.values]
        e = attach(Ts.reset_index(drop=True), g, df, tf, 'entry')
        table(e, 'short', '2. 每個趨勢訊號單獨進場')
        table(e, 'short_net', '   同上，改用 net GEX 正負分（負 = short gamma）')
        table(e[~e.cash], 'short', '   只看夜盤')
        table(e[e.cash], 'short', '   只看現金盤')
    rth(one, g)


def rth(one, g):
    df, t = oc.nq_rth(one, detail=True)
    t = t[t.date >= START].copy(); t['net'] = t.r3 - oc.COST / t.risk; t['entry'] = df.close.values[t.i.values]
    print(f'\nNQ RTH 1m（QQQ 做法，3R，{START} 起；只有現金盤）')
    table(attach(t.reset_index(drop=True), g, df, 1, 'entry'), 'short', '3. 用每小時 flip')
    q = pd.read_csv(os.path.join(HERE, 'data', 'zerogex', 'QQQ_minute.csv'), usecols=['ts', 'gamma_flip', 'close']).dropna()
    q['known'] = pd.to_datetime(q.ts, utc=True) + pd.Timedelta(minutes=1)
    nq = one.close.sort_index(); q['nq'] = nq.reindex(q.known - pd.Timedelta(minutes=1), method='ffill').values
    q['flip_nq'] = q.gamma_flip * q.nq / q.close; q['net_gex'] = np.nan
    table(attach(t.reset_index(drop=True), q.dropna(subset=['flip_nq']).sort_values('known'), df, 1, 'entry'), 'short', '   用每分鐘 flip')


if __name__ == '__main__':
    main()
