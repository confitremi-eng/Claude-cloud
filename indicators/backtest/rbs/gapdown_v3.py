"""v3's QQQ / NQ RTH 1-minute signals on big gap days: can they be traded when the open gaps down a lot?

  cd indicators/backtest
  python3 -I rbs/gapdown_v3.py [data.csv]          # default: data/NQ_1m_databento.csv; works on NQ_1m_5y.csv

Signals = v3's ETF setting on NQ cash-session 1m bars (stand-in for QQQ): (35, 0, 8, 1), Trend Judge 20 / 40 on the
signal's side, 1h EMA20, stop >= 0.95 ATR, slow line <= 7 ATR, NQ 2m Trend Judge not opposite, event windows, FOMC days.
Gap = 09:30 open vs the previous session's last close, %. Groups by gap; on gap-down days also longs / shorts and the
entry hour, and whether the ORB 5 long of gapdown_long.py came the same day. Each signal on its own (1R win %, 3R net R)
and one at a time (3R), 1 point cost.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import gapdown_long as gl

COST = 1.0
GROUPS = (('大低開 ≤ −0.75%', -99, -0.75), ('低開 −0.75 ~ −0.3%', -0.75, -0.3), ('平開 ±0.3%', -0.3, 0.3),
          ('高開 0.3 ~ 0.75%', 0.3, 0.75), ('大高開 ≥ 0.75%', 0.75, 99))


def signals(path):
    one = mm.read_csv(path); one['bad'] = False
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0))
    nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    df = mm.chart(cash, tdq, 1, 20.0, 40.0)
    t_open = pd.DatetimeIndex(df.last_min.values)
    t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
    s = mm.trend_signals(df, Hq, 1, 35, 8)
    k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
    s = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > 20.0)
          & (ndir[k] * s.side.values >= 0) & ~s.date.isin(ss.FOMC)].copy()
    et = pd.DatetimeIndex(df.datetime.values[s.i.values])
    et = (et.tz_localize('UTC') if et.tz is None else et).tz_convert(ss.NY) + pd.Timedelta(minutes=1)
    s['emin'] = et.hour * 60 + et.minute
    s['day'] = et.strftime('%Y-%m-%d')
    return s.sort_values('i'), cash


def day_gaps(cash):
    ny = cash.index.tz_convert(ss.NY); d = ny.strftime('%Y-%m-%d')
    g = pd.DataFrame({'o': cash.open.values, 'c': cash.close.values, 'd': d}).groupby('d')
    o, c = g.o.first(), g.c.last()
    return (100 * (o / c.shift(1) - 1)).dropna()


def line(lab, z):
    if not len(z): return f'    {lab:<22}   0 筆'
    n3 = z.r3 - COST / z.risk
    q = ss.seq(z, 3.0); nq = q.r3 - COST / q.risk
    return (f'    {lab:<22}{len(z):4d} 筆（{z.day.nunique():3d} 天） 1R 勝 {100 * (z.r1 > 0).mean():3.0f}%  3R 勝 {100 * (z.r3 > 0).mean():3.0f}% '
            f'每筆 {n3.mean():+.2f}R  ｜一次一筆 3R {len(q):3d} 筆 {nq.sum():+6.1f}R')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(mm.DATA, 'NQ_1m_databento.csv')
    s, cash = signals(path)
    gaps = day_gaps(cash); s['gap'] = s.day.map(gaps)
    s = s.dropna(subset=['gap'])
    print(f'{os.path.basename(path)}：v3 QQQ / NQ RTH 1m 訊號 {len(s)} 個，{s.day.nunique()} 天有訊號；扣 {COST:g} 點')

    print('\n######## 1. 依當天開盤缺口')
    for lab, a, b in GROUPS:
        days = int(((gaps > a) & (gaps <= b)).sum())
        print(line(f'{lab}（{days} 天）', s[(s.gap > a) & (s.gap <= b)]))

    big = s[s.gap <= -0.75]
    print('\n######## 2. 大低開（≤ −0.75%）細看')
    for k, nm in ((1, '做多'), (-1, '做空')):
        print(line(nm, big[big.side == k]))
    for a, b, nm in ((570, 660, '10:00–11:00 進場'), (660, 780, '11:00–13:00'), (780, 961, '13:00–16:00')):
        z = big[(big.emin >= a) & (big.emin < b)]
        print(line(nm, z))
        for k, sn in ((1, '多'), (-1, '空')):
            print(line(f'  其中{sn}', z[z.side == k]))
    one = gl.load(path); t, _ = gl.build(one)
    orb = set(t[(t.setup == 'ORB 5') & (t.gap <= -0.75)].date)
    print(line('ORB 5 有做多的那幾天', big[big.day.isin(orb)]))
    print(line('ORB 5 沒觸發的那幾天', big[~big.day.isin(orb)]))
    print('\n  對照：平開日的多 / 空')
    flat = s[(s.gap > -0.3) & (s.gap <= 0.3)]
    for k, nm in ((1, '做多'), (-1, '做空')):
        print(line(nm, flat[flat.side == k]))

    days = sorted(s.day.unique()); mid = days[len(days) // 2]
    print('\n######## 3. 大低開，前後半')
    for nm, z in (('前半', big[big.day < mid]), ('後半', big[big.day >= mid])):
        print(line(nm, z))
        for k, sn in ((1, '多'), (-1, '空')):
            print(line(f'  其中{sn}', z[z.side == k]))


if __name__ == '__main__':
    main()
